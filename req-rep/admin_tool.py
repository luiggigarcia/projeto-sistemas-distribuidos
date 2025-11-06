#!/usr/bin/env python3

import argparse
import zmq
import msgpack
import time
import json

REFERENCE_ADDR = "reference:5560"
PUBSUB_PROXY_XSUB = "proxy_pubsub:5557"


def call_reference_list(timeout=3.0):
    ctx = zmq.Context()
    s = ctx.socket(zmq.REQ)
    s.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
    s.setsockopt(zmq.SNDTIMEO, int(timeout * 1000))
    s.connect(f"tcp://{REFERENCE_ADDR}")
    req = {"service": "list", "data": {"timestamp": time.strftime("%H:%M:%S"), "clock": 0}}
    try:
        s.send(msgpack.packb(req, use_bin_type=True))
        raw = s.recv()
        try:
            reply = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            reply = json.loads(raw.decode('utf-8'))
    except Exception as e:
        print("Erro ao contatar reference:", e)
        reply = None
    finally:
        try:
            s.close()
            ctx.term()
        except Exception:
            pass
    return reply


def admin_req(address, msg, timeout=3.0):
    ctx = zmq.Context()
    s = ctx.socket(zmq.REQ)
    s.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
    s.setsockopt(zmq.SNDTIMEO, int(timeout * 1000))
    s.connect(f"tcp://{address}")
    try:
        s.send(msgpack.packb(msg, use_bin_type=True))
        raw = s.recv()
        try:
            reply = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            reply = json.loads(raw.decode('utf-8'))
    except Exception as e:
        reply = {"error": str(e)}
    finally:
        try:
            s.close()
            ctx.term()
        except Exception:
            pass
    return reply


def publish_servers_topic(payload):
    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    try:
        pub.connect(f"tcp://{PUBSUB_PROXY_XSUB}")
        time.sleep(0.12)
        pub.send_string(f"servers {json.dumps(payload)}")
    except Exception as e:
        print("Erro ao publicar no proxy_pubsub:", e)
        return False
    finally:
        try:
            pub.close()
            ctx.term()
        except Exception:
            pass
    return True


def list_servers():
    r = call_reference_list()
    if r is None:
        print("Sem resposta do reference")
        return []
    data = r.get('data', {})
    lst = data.get('list', [])
    normalized = []
    for s in lst:
        normalized.append({
            'name': s.get('name'),
            'rank': s.get('rank'),
            'address': s.get('address')
        })
    print(json.dumps(normalized, indent=2, ensure_ascii=False))
    return normalized


def poll_clock_all():
    servers = list_servers()
    if not servers:
        print("Nenhum servidor retornado pelo reference")
        return
    for s in servers:
        name = s.get('name')
        rank = s.get('rank')
        addr = s.get('address') or f"{name}:{5600 + int(rank)}"
        print(f"-> Perguntando clock a {name} ({addr})")
        req = {"service": "clock", "data": {"timestamp": time.strftime('%H:%M:%S'), "clock": 0}}
        reply = admin_req(addr, req, timeout=2.0)
        print(name, reply)


def send_election(target=None, send_all=False):
    servers = list_servers()
    if not servers:
        print("Nenhum servidor para election")
        return
    targets = []
    if send_all:
        targets = servers
    elif target:
        targets = [s for s in servers if s.get('name') == target]
        if not targets:
            print("Servidor alvo não encontrado no reference list")
            return
    else:
        print("Especifique --server ou --all")
        return
    for s in targets:
        name = s.get('name')
        rank = s.get('rank')
        addr = s.get('address') or f"{name}:{5600 + int(rank)}"
        print(f"Enviando election para {name} ({addr})")
        req = {"service": "election", "data": {"timestamp": time.strftime('%H:%M:%S'), "clock": 0}}
        reply = admin_req(addr, req, timeout=2.0)
        # print a clearer election result including any coordinator announcement
        if not reply:
            print(name, {'error': 'no reply'})
            continue
        d = reply.get('data', {}) if isinstance(reply, dict) else {}
        coord = d.get('coordinator')
        if coord:
            print(name, 'REPORTS_COORDINATOR ->', coord)
        else:
            print(name, reply)


def set_clock(target, tval):
    servers = list_servers()
    if not servers:
        print("Nenhum servidor para set-clock")
        return
    targets = [s for s in servers if s.get('name') == target]
    if not targets:
        print("Servidor alvo não encontrado")
        return
    s = targets[0]
    name = s.get('name')
    rank = s.get('rank')
    addr = s.get('address') or f"{name}:{5600 + int(rank)}"
    print(f"Enviando set-clock(time={tval}) para {name} @ {addr}")
    req = {"service": "clock", "data": {"time": float(tval), "timestamp": time.strftime('%H:%M:%S'), "clock": 0}}
    reply = admin_req(addr, req, timeout=2.0)
    print(reply)


def announce_coordinator(name):
    payload = {"service": "election", "data": {"coordinator": name, "timestamp": time.strftime('%H:%M:%S'), "clock": 0}}
    ok = publish_servers_topic(payload)
    print("announcement sent?", ok)


def main():
    parser = argparse.ArgumentParser(description='Admin tool for reference and servers')
    sub = parser.add_subparsers(dest='cmd')

    sub.add_parser('list', help='List servers from reference')
    sub.add_parser('poll-clock', help='Poll clock from all servers')

    p_election = sub.add_parser('election', help='Send election request')
    p_election.add_argument('--server', help='Server name (e.g. servidor1)')
    p_election.add_argument('--all', action='store_true', help='Send to all servers')

    p_set = sub.add_parser('set-clock', help='Set/adjust clock on a server')
    p_set.add_argument('--server', required=True, help='Server name')
    p_set.add_argument('--time', required=True, help='Unix epoch float time to set')

    p_ann = sub.add_parser('announce', help='Announce coordinator via pubsub')
    p_ann.add_argument('--coordinator', required=True, help='Coordinator name')

    args = parser.parse_args()
    if args.cmd == 'list':
        list_servers()
    elif args.cmd == 'poll-clock':
        poll_clock_all()
    elif args.cmd == 'election':
        send_election(target=args.server, send_all=args.all)
    elif args.cmd == 'set-clock':
        set_clock(args.server, args.time)
    elif args.cmd == 'announce':
        announce_coordinator(args.coordinator)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
