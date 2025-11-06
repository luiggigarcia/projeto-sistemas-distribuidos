#!/usr/bin/env python3

import os
import time
import json
import threading
import msgpack
import zmq

# Storage file for registered servers
STORAGE_DIR = os.environ.get('STORAGE_DIR', os.path.join(os.path.dirname(__file__), 'storage-server'))
SERVERS_FILE = os.path.join(STORAGE_DIR, 'servers.txt')

HEARTBEAT_TIMEOUT = 30.0 


def ensure_storage():
    os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
            f.write('[]')


def load_servers():
    try:
        with open(SERVERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
    except Exception:
        return []


def save_servers(servers):
    try:
        with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print('Erro salvando servers:', e)


def find_server_by_name(servers, name):
    for s in servers:
        if s.get('name') == name:
            return s
    return None


def assign_rank(servers):
    used = {int(s.get('rank')) for s in servers if s.get('rank') is not None}
    r = 1
    while r in used:
        r += 1
    return r


def cleanup_expired(servers):
    now = time.time()
    alive = []
    for s in servers:
        last = s.get('last_seen', 0)
        if now - float(last) <= HEARTBEAT_TIMEOUT:
            alive.append(s)
    return alive


class ReferenceServer:
    def __init__(self, bind_addr='tcp://*:5560'):
        ensure_storage()
        self.bind_addr = bind_addr
        self.coordinator = None
        self.lock = threading.Lock()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(bind_addr)

    def start(self):
        print('Reference listening on', self.bind_addr)
        t = threading.Thread(target=self._serve_loop, daemon=True)
        t.start()
        # menu loop if interactive
        try:
            if os.isatty(0):
                self.menu_loop()
            else:
                # keep main thread alive
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print('Shutting down reference')

    def _serve_loop(self):
        while True:
            try:
                raw = self.socket.recv()
                try:
                    req = msgpack.unpackb(raw, raw=False, strict_map_key=False)
                except Exception:
                    try:
                        req = json.loads(raw.decode('utf-8'))
                    except Exception:
                        req = None
                if req is None:
                    reply = {'service': 'error', 'data': {'message': 'invalid payload', 'timestamp': time.time(), 'clock': 0}}
                else:
                    reply = self.handle_request(req)
                # reply as msgpack
                try:
                    self.socket.send(msgpack.packb(reply, use_bin_type=True))
                except Exception:
                    self.socket.send(json.dumps(reply).encode('utf-8'))
            except Exception as e:
                # keep serving even on errors
                print('Reference serve loop error:', e)

    def handle_request(self, req):
        svc = req.get('service')
        data = req.get('data', {})
        now = time.time()
        # load servers
        with self.lock:
            servers = load_servers()

            if svc == 'rank':
                name = data.get('user')
                address = data.get('address') or data.get('addr')
                # find or assign
                s = find_server_by_name(servers, name)
                if s is None:
                    rank = assign_rank(servers)
                    s = {'name': name, 'rank': rank, 'address': address, 'last_seen': now}
                    servers.append(s)
                    save_servers(servers)
                else:
                    # update address/last_seen
                    if address:
                        s['address'] = address
                    s['last_seen'] = now
                    save_servers(servers)
                return {'service': 'rank', 'data': {'rank': s['rank'], 'timestamp': now, 'clock': 0}}

            elif svc == 'list':
                # cleanup expired before returning
                servers = cleanup_expired(servers)
                save_servers(servers)
                simple = [{'name': s.get('name'), 'rank': s.get('rank'), 'address': s.get('address')} for s in servers]
                return {'service': 'list', 'data': {'list': simple, 'timestamp': now, 'clock': 0}}

            elif svc == 'heartbeat':
                name = data.get('user')
                address = data.get('address') or data.get('addr')
                s = find_server_by_name(servers, name)
                if s is None:
                    rank = assign_rank(servers)
                    s = {'name': name, 'rank': rank, 'address': address, 'last_seen': now}
                    servers.append(s)
                else:
                    s['last_seen'] = now
                    if address:
                        s['address'] = address
                save_servers(servers)
                return {'service': 'heartbeat', 'data': {'timestamp': now, 'clock': 0}}

            elif svc == 'clock':
                # return server time
                return {'service': 'clock', 'data': {'time': now, 'timestamp': now, 'clock': 0}}

            elif svc == 'election':
                # if coordinator announced in the request, update and reply with coordinator
                coord = data.get('coordinator')
                if coord:
                    self.coordinator = coord
                    return {'service': 'election', 'data': {'coordinator': coord, 'timestamp': now, 'clock': 0}}
                # otherwise, acknowledge election request
                return {'service': 'election', 'data': {'election': 'OK', 'timestamp': now, 'clock': 0}}

            else:
                return {'service': 'error', 'data': {'message': 'unknown service', 'timestamp': now, 'clock': 0}}

    def menu_loop(self):
        print('\nReference admin menu (type help for commands)')
        while True:
            try:
                cmd = input('ref> ').strip()
            except EOFError:
                break
            if not cmd:
                continue
            if cmd in ('q', 'quit', 'exit'):
                print('Exiting menu')
                break
            if cmd in ('h', 'help'):
                print('\nCommands:')
                print('  list            - show registered servers')
                print('  save            - persist servers to file')
                print('  cleanup         - remove expired servers')
                print('  show <name>     - show server details')
                print('  announce <name> - set coordinator to <name>')
                print('  help            - show this help')
                print('  quit            - exit')
                continue
            parts = cmd.split()
            if parts[0] == 'list':
                with self.lock:
                    servers = load_servers()
                    servers = cleanup_expired(servers)
                    print(json.dumps(servers, indent=2, ensure_ascii=False))
            elif parts[0] == 'save':
                with self.lock:
                    servers = load_servers()
                    save_servers(servers)
                    print('saved')
            elif parts[0] == 'cleanup':
                with self.lock:
                    servers = load_servers()
                    servers = cleanup_expired(servers)
                    save_servers(servers)
                    print('cleanup done')
            elif parts[0] == 'show' and len(parts) > 1:
                name = parts[1]
                with self.lock:
                    servers = load_servers()
                    s = find_server_by_name(servers, name)
                    print(json.dumps(s or {}, indent=2, ensure_ascii=False))
            elif parts[0] == 'announce' and len(parts) > 1:
                name = parts[1]
                self.coordinator = name
                print('coordinator set to', name)
            else:
                print('unknown command; type help')


if __name__ == '__main__':
    ref = ReferenceServer(bind_addr='tcp://*:5560')
    ref.start()
import time
import zmq
import msgpack
from datetime import datetime, timedelta, timezone
import threading

# Simple reference service: keeps server list with ranks and provides rank/list/heartbeat services
br_tz = timezone(timedelta(hours=-3))

context = zmq.Context()
sock = context.socket(zmq.REP)
sock.bind("tcp://0.0.0.0:5560")

servers = {}  # name -> {rank: int, last_seen: timestamp, address: str}
next_rank = 1
lock = threading.Lock()

def cleanup_loop(interval=10, expire=20):
    while True:
        now = time.time()
        with lock:
            to_delete = [n for n,v in servers.items() if now - v.get('last_seen',0) > expire]
            for n in to_delete:
                del servers[n]
        time.sleep(interval)

cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
cleanup_thread.start()

print("Reference service started on 5560")
while True:
    raw = sock.recv()
    try:
        try:
            req = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            import json as _json
            req = _json.loads(raw.decode('utf-8'))
        svc = req.get('service')
        data = req.get('data', {})
        now_ts = datetime.now(br_tz).strftime('%H:%M:%S')
        # extract clock from data if present
        clk = data.get('clock') if isinstance(data, dict) else None
        if svc == 'rank':
            name = data.get('user')
            address = data.get('address')
            if not name:
                reply = {'service':'rank','data':{'rank':None,'timestamp':now_ts,'clock':clk}}
            else:
                with lock:
                    if name not in servers:
                        servers[name] = {'rank': next_rank, 'last_seen': time.time(), 'address': address}
                        assigned = next_rank
                        next_rank += 1
                    else:
                        # update last_seen and optionally address
                        servers[name]['last_seen'] = time.time()
                        if address:
                            servers[name]['address'] = address
                        assigned = servers[name]['rank']
                reply = {'service':'rank','data':{'rank': assigned,'timestamp':now_ts,'clock':clk}}
        elif svc == 'list':
            with lock:
                lst = [{'name': n, 'rank': v['rank'], 'address': v.get('address')} for n,v in servers.items()]
            reply = {'service':'list','data':{'list': lst,'timestamp':now_ts,'clock':clk}}
        elif svc == 'heartbeat':
            name = data.get('user')
            address = data.get('address')
            if name:
                with lock:
                    if name in servers:
                        servers[name]['last_seen'] = time.time()
                        if address:
                            servers[name]['address'] = address
                    else:
                        servers[name] = {'rank': next_rank, 'last_seen': time.time(), 'address': address}
                        next_rank += 1
            reply = {'service':'heartbeat','data':{'timestamp':now_ts,'clock':clk}}
        else:
            reply = {'service':'error','data':{'status':'erro','message':'servico desconhecido','timestamp':now_ts,'clock':clk}}
    except Exception as e:
        reply = {'service':'error','data':{'status':'erro','message':str(e),'timestamp':now_ts}}
    try:
        sock.send(msgpack.packb(reply, use_bin_type=True))
    except Exception:
        import json as _json
        sock.send(_json.dumps(reply).encode('utf-8'))
