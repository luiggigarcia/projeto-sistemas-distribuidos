import os
import zmq
import time
import msgpack
import threading
import socket as pysocket
import json
from datetime import datetime, timedelta, timezone

br_tz = timezone(timedelta(hours=-3))

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.connect("tcp://broker:5556")

logical_clock = 0
app_time = time.time()
message_count = 0
coordinator_name = None

SERVER_NAME = os.environ.get("SERVER_NAME") or pysocket.gethostname()

REFERENCE_ADDR = os.environ.get("REFERENCE_ADDR", "reference:5560")

admin_port = None

SERVER_ADDR = None

def update_clock_on_receive(received):
    global logical_clock
    try:
        if received is None:
            return
        r = int(received)
        if r > logical_clock:
            logical_clock = r
    except Exception:
        pass

def increment_clock_before_send():
    global logical_clock
    logical_clock += 1
    return logical_clock

def send_req_to_reference(req_msg):
    """Send a REQ to the reference service and return the unpacked reply map."""
    try:
        ctx = zmq.Context()
        s = ctx.socket(zmq.REQ)
        s.connect(f"tcp://{REFERENCE_ADDR}")
        now_ts = datetime.now(br_tz).strftime("%H:%M:%S")
        c = increment_clock_before_send()
        data = req_msg.get("data", {})
        data["clock"] = c
        data["timestamp"] = now_ts
        msg = {"service": req_msg.get("service"), "data": data}
        s.send(msgpack.packb(msg, use_bin_type=True), 0)
        raw = s.recv()
        try:
            reply = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            import json as _json
            reply = _json.loads(raw.decode('utf-8'))
        try:
            rdata = reply.get("data", {})
            rc = rdata.get("clock")
            update_clock_on_receive(rc)
        except Exception:
            pass
        try:
            s.close()
            ctx.term()
        except Exception:
            pass
        return reply
    except Exception as e:
        return {"service": "error", "data": {"status": "erro", "message": str(e)}}

def heartbeat_loop(interval=5):
    while True:
        try:
            data = {"user": SERVER_NAME}
            if SERVER_ADDR:
                data["address"] = SERVER_ADDR
            req = {"service": "heartbeat", "data": data}
            send_req_to_reference(req)
        except Exception:
            pass
        time.sleep(interval)

try:
    rank_reply = send_req_to_reference({"service": "rank", "data": {"user": SERVER_NAME}})
    server_rank = rank_reply.get("data", {}).get("rank")
except Exception:
    server_rank = None

# start heartbeat thread
def send_req_to_server(address, msg, timeout=3):
    """Send a REQ to another server admin endpoint and return unpacked reply or None on error."""
    try:
        ctx = zmq.Context()
        s = ctx.socket(zmq.REQ)
        s.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
        s.setsockopt(zmq.SNDTIMEO, int(timeout * 1000))
        s.connect(f"tcp://{address}")
        s.send(msgpack.packb(msg, use_bin_type=True))
        raw = s.recv()
        try:
            reply = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            reply = json.loads(raw.decode('utf-8'))
        try:
            s.close()
            ctx.term()
        except Exception:
            pass
        return reply
    except Exception:
        return None


def publish_announcement(topic, payload):
    try:
        pub_ctx = zmq.Context()
        pub = pub_ctx.socket(zmq.PUB)
        pub.connect("tcp://proxy_pubsub:5557")
        # publish as: "topic <json>"
        pub.send_string(f"{topic} {json.dumps(payload)}")
        pub.close()
        pub_ctx.term()
    except Exception:
        pass


def maybe_trigger_sync():
    global coordinator_name
    try:
        if coordinator_name == SERVER_NAME:
            perform_berkeley_sync()
        else:
            # check coordinator presence via reference list
            try:
                lst = send_req_to_reference({"service": "list", "data": {}})
                servers = lst.get("data", {}).get("list", [])
                coords = [s for s in servers if s.get("name") == coordinator_name]
                if not coordinator_name or not coords:
                    perform_election()
            except Exception:
                perform_election()
    except Exception:
        pass


def perform_berkeley_sync():
    """Coordinator polls servers for their app_time, computes average and instructs adjustments."""
    global app_time, logical_clock
    try:
        lst_reply = send_req_to_reference({"service": "list", "data": {}})
        servers_list = lst_reply.get("data", {}).get("list", [])
        times = []
        addresses = []
        times.append(app_time)
        for s in servers_list:
            name = s.get('name')
            rank = s.get('rank')
            addr = s.get('address') or f"{name}:{5600 + rank}"
            if name == SERVER_NAME:
                continue
            addresses.append((name, addr))
            req = {"service": "clock", "data": {"timestamp": datetime.now(br_tz).strftime('%H:%M:%S'), "clock": logical_clock}}
            reply = send_req_to_server(addr, req, timeout=3)
            if reply and isinstance(reply.get('data',{}).get('time'), (int, float)):
                times.append(float(reply['data']['time']))
        if not times:
            return
        avg = sum(times) / len(times)
        
        for s in servers_list:
            name = s.get('name')
            rank = s.get('rank')
            addr = s.get('address') or f"{name}:{5600 + rank}"
            req2 = {"service": "clock", "data": {"time": avg, "timestamp": datetime.now(br_tz).strftime('%H:%M:%S'), "clock": increment_clock_before_send()}}
            # send instruction; ignore replies
            if name == SERVER_NAME:
                app_time = avg
            else:
                try:
                    send_req_to_server(addr, req2, timeout=3)
                except Exception:
                    pass
    except Exception:
        pass


def perform_election():
    """Deterministic election: choose the server with the highest numeric rank as coordinator
    and publish an announcement. Every participant runs the same logic so they converge
    to the same coordinator (no multi-round protocol required for this demo).
    """
    global coordinator_name
    try:
        lst_reply = send_req_to_reference({"service": "list", "data": {}})
        servers_list = lst_reply.get("data", {}).get("list", [])
        if not servers_list:
            return
        # choose server with highest numeric rank (convert ranks to int)
        winner = None
        max_rank = None
        for s in servers_list:
            try:
                r = int(s.get('rank'))
            except Exception:
                continue
            if max_rank is None or r > max_rank:
                max_rank = r
                winner = s
        if winner:
            winner_name = winner.get('name')
            coordinator_name = winner_name
            announce = {"service": "election", "data": {"coordinator": winner_name, "timestamp": datetime.now(br_tz).strftime('%H:%M:%S'), "clock": increment_clock_before_send()}}
            # publish announcement so all subscribers update their local coordinator_name
            publish_announcement('servers', announce)
    except Exception:
        pass


def admin_server_loop(port):
    global app_time, logical_clock, coordinator_name
    try:
        admin_ctx = zmq.Context()
        rep = admin_ctx.socket(zmq.REP)
        rep.bind(f"tcp://0.0.0.0:{port}")
        while True:
            raw = rep.recv()
            try:
                try:
                    req = msgpack.unpackb(raw, raw=False, strict_map_key=False)
                except Exception:
                    req = json.loads(raw.decode('utf-8'))
                svc = req.get('service')
                data = req.get('data', {})
                now_ts = datetime.now(br_tz).strftime('%H:%M:%S')
                if svc == 'clock':
                    # If data contains 'time' -> this is an adjustment instruction
                    if 'time' in data:
                        try:
                            app_time = float(data.get('time'))
                        except Exception:
                            pass
                        reply = {'service': 'clock', 'data': {'time': app_time, 'timestamp': now_ts, 'clock': logical_clock}}
                    else:
                        reply = {'service': 'clock', 'data': {'time': app_time, 'timestamp': now_ts, 'clock': logical_clock}}
                elif svc == 'election':
                    # If the request contains a coordinator announcement, update local coordinator
                    coord_in = data.get('coordinator')
                    if coord_in:
                        coordinator_name = coord_in
                        reply = {'service': 'election', 'data': {'coordinator': coordinator_name, 'timestamp': now_ts, 'clock': logical_clock}}
                    else:
                        # acknowledge election request and return current coordinator (if any)
                        reply = {'service': 'election', 'data': {'election': 'OK', 'coordinator': coordinator_name, 'timestamp': now_ts, 'clock': logical_clock}}
                else:
                    reply = {'service': 'error', 'data': {'status': 'erro', 'message': 'servico desconhecido', 'timestamp': now_ts, 'clock': logical_clock}}
            except Exception as e:
                reply = {'service': 'error', 'data': {'status': 'erro', 'message': str(e), 'timestamp': now_ts}}
            try:
                rep.send(msgpack.packb(reply, use_bin_type=True))
            except Exception:
                rep.send(json.dumps(reply).encode('utf-8'))
    except Exception:
        pass


def sub_servers_loop():
    # subscribe to 'servers' topic to learn about elections/coord announcements
    try:
        sub_ctx = zmq.Context()
        sub = sub_ctx.socket(zmq.SUB)
        sub.connect("tcp://proxy_pubsub:5558")
        sub.setsockopt_string(zmq.SUBSCRIBE, "servers")
        while True:
            try:
                raw = sub.recv_string()
                # raw looks like: "servers {json}"
                parts = raw.split(' ', 1)
                if len(parts) < 2:
                    continue
                payload = json.loads(parts[1])
                svc = payload.get('service')
                data = payload.get('data', {})
                if svc == 'election':
                    coord = data.get('coordinator')
                    if coord:
                        # update coordinator name
                        global coordinator_name
                        coordinator_name = coord
            except Exception:
                time.sleep(0.1)
    except Exception:
        pass

# On startup, ask reference for rank and register


def pretty_print(service, data):
    # Simple pretty printer for server logs: prints tables for common services
    try:
        if service == "login":
            status = data.get("status")
            desc = data.get("description", "")
            ts = data.get("timestamp", "")
            user = data.get("user") or data.get("username")
            print(f"[LOGIN] status={status} time={ts} desc={desc}")
            if user:
                print(f"-> Usuário '{user}' está logado")
        elif service == "users":
            users = data.get("users", [])
            ts = data.get("timestamp", "")
            print(f"[USERS] timestamp={ts} count={len(users)}")
            if users:
                print("+------------------------------+")
                print("|     Usuários cadastrados     |")
                print("+------------------------------+")
                for i, u in enumerate(users, start=1):
                    print(f" {i:2d}. {u}")
                print("+------------------------------+")
            else:
                print("(nenhum usuário cadastrado)")
        elif service == "channels":
            channels = data.get("channels", [])
            ts = data.get("timestamp", "")
            print(f"[CHANNELS] timestamp={ts} count={len(channels)}")
            if channels:
                print("+------------------------------+")
                print("|       Canais cadastrados     |")
                print("+------------------------------+")
                for i, c in enumerate(channels, start=1):
                    print(f" {i:2d}. {c}")
                print("+------------------------------+")
            else:
                print("(nenhum canal cadastrado)")
        elif service in ("publish", "message"):
            status = data.get("status")
            msg = data.get("message") if service == "publish" else data.get("message")
            ts = data.get("timestamp", "")
            print(f"[{service.upper()}] status={status} time={ts} msg={msg}")
        else:
            # Generic pretty print for unknown services
            print(f"[REPLY] service={service} data={data}")
    except Exception as e:
        print("[pretty_print] erro ao imprimir resposta:", e)


# assign admin port based on rank if possible
try:
    if server_rank:
        admin_port = 5600 + int(server_rank)
    else:
        admin_port = 5600
    SERVER_ADDR = f"{SERVER_NAME}:{admin_port}"
    # start admin server
    admin_thread = threading.Thread(target=admin_server_loop, args=(admin_port,), daemon=True)
    admin_thread.start()
    # start subscriber to servers topic
    sub_thread = threading.Thread(target=sub_servers_loop, daemon=True)
    sub_thread.start()
    # start heartbeat thread (now we can include address)
    hb_thread = threading.Thread(target=heartbeat_loop, args=(5,), daemon=True)
    hb_thread.start()
except Exception:
    pass

while True:
    try:
        # receive raw bytes and unpack with MessagePack
        raw = socket.recv()
        try:
            request = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            # fallback to json decode for compatibility
            import json as _json
            request = _json.loads(raw.decode('utf-8'))
        # Update logical clock from incoming message if it has one
        try:
            incoming_clock = None
            if isinstance(request, dict):
                incoming_clock = request.get("data", {}).get("clock")
            update_clock_on_receive(incoming_clock)
        except Exception:
            pass
        service = request.get("service")

        if service == "message":
            dados = request["data"]
            src = dados.get("src")
            dst = dados.get("dst")
            message = dados.get("message")
            timestamp = dados.get("timestamp")
            status = "OK"
            error_msg = ""
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            # Verifica se usuário de destino existe
            usuarios_existentes = set()
            try:
                with open("/app/storage-server/logins.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        u = line.strip().split(",")[0]
                        if u:
                            usuarios_existentes.add(u)
            except FileNotFoundError:
                pass
            if not dst or dst not in usuarios_existentes:
                status = "erro"
                error_msg = "Usuário de destino não existe."
            else:
                # Publica mensagem no tópico do usuário de destino via Pub/Sub
                try:
                    pub_context = zmq.Context()
                    pub_socket = pub_context.socket(zmq.PUB)
                    pub_socket.connect("tcp://proxy_pubsub:5557")
                    # increment clock before sending this outgoing pub/sub message
                    c_pub = increment_clock_before_send()
                    pub_socket.send_string(f"{dst} {src}: {message} [{time_br}] (clock={c_pub})")
                    pub_socket.close()
                    pub_context.term()
                    # Salva histórico
                    with open("/app/storage-server/historico_msg.txt", "a", encoding="utf-8") as f:
                        f.write(f"{src},{dst},{message},{time_br},{c_pub}\n")
                    # Log explícito de envio de mensagem para o terminal do servidor
                    try:
                        print(f"[SEND] {src} -> {dst}: {message} [{time_br}]")
                    except Exception:
                        pass
                except Exception as e:
                    status = "erro"
                    error_msg = f"Erro ao enviar mensagem: {str(e)}"
            # prepare reply and include logical clock
            c = increment_clock_before_send()
            reply = {
                "service": "message",
                "data": {
                    "status": status,
                    "message": error_msg,
                    "timestamp": time_br,
                    "clock": c
                }
            }
            # pretty print and send packed with MessagePack
            pretty_print(reply.get("service"), reply.get("data", {}))
            try:
                socket.send(msgpack.packb(reply, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(reply).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            continue

        elif service == "login":
            dados = request["data"]
            user = dados.get("user")
            timestamp = dados.get("timestamp")
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")

            if not timestamp:
                timestamp = time_br

            if not user or not timestamp:
                reply = {
                    "service": "login",
                    "data": {
                        "status": "erro",
                        "timestamp": time_br,
                        "description": "Dados de login inválidos: 'user' ou 'timestamp' ausente."
                    }
                }
                pretty_print(reply.get("service"), reply.get("data", {}))
                try:
                    socket.send(msgpack.packb(reply, use_bin_type=True))
                    message_count += 1
                    if message_count % 10 == 0:
                        threading.Thread(target=maybe_trigger_sync, daemon=True).start()
                except Exception:
                    import json as _json
                    socket.send(_json.dumps(reply).encode('utf-8'))
                    message_count += 1
                    if message_count % 10 == 0:
                        threading.Thread(target=maybe_trigger_sync, daemon=True).start()
                continue

            # Verifica se usuário já está cadastrado
            user_exists = False
            try:
                with open("/app/storage-server/logins.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        existing = line.strip().split(",")[0]
                        if existing == user:
                            user_exists = True
                            break
            except FileNotFoundError:
                user_exists = False

            if user_exists:
                c = increment_clock_before_send()
                reply = {
                    "service": "login",
                    "data": {
                        "status": "logado",
                        "timestamp": time_br,
                        "description": f"Usuário '{user}' já está cadastrado e logado.",
                        "clock": c,
                        "user": user
                    }
                }
                try:
                    socket.send(msgpack.packb(reply, use_bin_type=True))
                except Exception:
                    import json as _json
                    socket.send(_json.dumps(reply).encode('utf-8'))
                continue

            # usuário não existe -> registra e responde sucesso
            try:
                # ensure storage dir exists inside container
                os.makedirs("/app/storage-server", exist_ok=True)
                with open("/app/storage-server/logins.txt", "a", encoding="utf-8") as f:
                    f.write(f"{user},{timestamp}\n")
                c = increment_clock_before_send()
                reply = {
                    "service": "login",
                    "data": {
                        "status": "sucesso",
                        "timestamp": time_br,
                        "description": "Login registrado com sucesso.",
                        "clock": c,
                        "user": user
                    }
                }
            except Exception as e:
                reply = {
                    "service": "login",
                    "data": {
                        "status": "erro",
                        "timestamp": time_br,
                        "description": f"Erro ao gravar arquivo: {str(e)}"
                    }
                }
            pretty_print(reply.get("service"), reply.get("data", {}))
            try:
                socket.send(msgpack.packb(reply, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(reply).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            continue

        elif service == "users":
            dados = request["data"]
            users = []
            try:
                with open("/app/storage-server/logins.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        user = line.strip().split(",")[0]
                        if user:
                            users.append(user)
            except FileNotFoundError:
                users = []
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            c = increment_clock_before_send()
            reply = {
                "service": "users",
                "data": {
                    "timestamp": time_br,
                    "users": users,
                    "clock": c
                }
            }
            pretty_print(reply.get("service"), reply.get("data", {}))
            try:
                socket.send(msgpack.packb(reply, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(reply).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            continue

        elif service == "channel":
            dados = request["data"]
            channel = dados.get("channel")
            timestamp = dados.get("timestamp")
            status = "sucesso"
            description = ""
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            if not channel or not timestamp:
                status = "erro"
                description = "Dados de canal inválidos: 'channel' ou 'timestamp' ausente."
            else:
                try:
                    # ensure storage dir exists
                    os.makedirs("/app/storage-server", exist_ok=True)
                    with open("/app/storage-server/channels.txt", "a", encoding="utf-8") as f:
                        f.write(f"{channel},{timestamp}\n")
                except Exception as e:
                    status = "erro"
                    description = f"Erro ao gravar canal: {str(e)}"
            c = increment_clock_before_send()
            reply = {
                "service": "channel",
                "data": {
                    "status": status,
                    "timestamp": time_br,
                    "description": description,
                    "clock": c
                }
            }
            pretty_print(reply.get("service"), reply.get("data", {}))
            try:
                socket.send(msgpack.packb(reply, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(reply).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            continue

        elif service == "channels":
            dados = request["data"]
            channels = []
            try:
                with open("/app/storage-server/channels.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        channel = line.strip().split(",")[0]
                        if channel:
                            channels.append(channel)
            except FileNotFoundError:
                channels = []
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            c = increment_clock_before_send()
            reply = {
                "service": "channels",
                "data": {
                    "timestamp": time_br,
                    "channels": channels,
                    "clock": c
                }
            }
            pretty_print(reply.get("service"), reply.get("data", {}))
            try:
                socket.send(msgpack.packb(reply, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(reply).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            continue

        elif service == "publish":
            dados = request["data"]
            user = dados.get("user")
            channel = dados.get("channel")
            message = dados.get("message")
            timestamp = dados.get("timestamp")
            status = "OK"
            error_msg = ""
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            # Verifica se canal existe
            canais_existentes = set()
            try:
                with open("/app/storage-server/channels.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        c = line.strip().split(",")[0]
                        if c:
                            canais_existentes.add(c)
            except FileNotFoundError:
                pass
            if not channel or channel not in canais_existentes:
                status = "erro"
                error_msg = "Canal não existe."
            else:
                # Publica mensagem no canal via Pub/Sub
                try:
                    pub_context = zmq.Context()
                    pub_socket = pub_context.socket(zmq.PUB)
                    pub_socket.connect("tcp://proxy_pubsub:5557")
                    # increment logical clock before publishing to channel
                    c_pub = increment_clock_before_send()
                    pub_socket.send_string(f"{channel} {user}: {message} [{time_br}] (clock={c_pub})")
                    pub_socket.close()
                    pub_context.term()
                    # Salva histórico
                    os.makedirs("/app/storage-server", exist_ok=True)
                    with open("/app/storage-server/historico_pubsub.txt", "a", encoding="utf-8") as f:
                        f.write(f"{channel},{user},{message},{time_br},{c_pub}\n")
                except Exception as e:
                    status = "erro"
                    error_msg = f"Erro ao publicar: {str(e)}"
            c = increment_clock_before_send()
            reply = {
                "service": "publish",
                "data": {
                    "status": status,
                    "message": error_msg,
                    "timestamp": time_br,
                    "clock": c
                }
            }
            pretty_print(reply.get("service"), reply.get("data", {}))
            try:
                socket.send(msgpack.packb(reply, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(reply).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            continue

        else:
            # Serviço desconhecido
            c = increment_clock_before_send()
            unknown = {"service": "error", "data": {"status": "erro", "message": "servico desconhecido", "clock": c}}
            try:
                socket.send(msgpack.packb(unknown, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(unknown).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            continue
    except Exception as e:
        import traceback
        print("Erro ao processar requisição:", str(e))
        traceback.print_exc()
        try:
            c = increment_clock_before_send()
            err_reply = {"service": "error", "data": {"status": "erro", "message": str(e), "clock": c}}
            try:
                socket.send(msgpack.packb(err_reply, use_bin_type=True))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
            except Exception:
                import json as _json
                socket.send(_json.dumps(err_reply).encode('utf-8'))
                message_count += 1
                if message_count % 10 == 0:
                    threading.Thread(target=maybe_trigger_sync, daemon=True).start()
        except Exception:
            pass
        continue