import os
import zmq
from datetime import datetime, timedelta, timezone

# Definir timezone de Brasília (UTC-3)
br_tz = timezone(timedelta(hours=-3))

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://broker:5555")

opcao = input("Entre com a opção: ")
while opcao != "sair":
    match opcao:
        case "login":
            import json
            user = input("Nome de usuário: ")
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            request = {
                "service": "login",
                "data": {
                    "user": user,
                    "timestamp": time_br
                }
            }
            socket.send_json(request)
            reply = socket.recv_json()
            print("Resposta do servidor:", json.dumps(reply, indent=2, ensure_ascii=False))
            print("Path: " + os.getcwd(), flush=True)

        case "users":
            import json
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            request = {
                "service": "users",
                "data": {
                    "timestamp": time_br
                }
            }
            socket.send_json(request)
            reply = socket.recv_json()
            print("Usuários cadastrados:", json.dumps(reply, indent=2, ensure_ascii=False))

        case "channel":
            import json
            channel = input("Nome do canal: ")
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            request = {
                "service": "channel",
                "data": {
                    "channel": channel,
                    "timestamp": time_br
                }
            }
            socket.send_json(request)
            reply = socket.recv_json()
            print("Resposta do servidor:", json.dumps(reply, indent=2, ensure_ascii=False))

        case "channels":
            import json
            time_br = datetime.now(br_tz).strftime("%H:%M:%S")
            request = {
                "service": "channels",
                "data": {
                    "timestamp": time_br
                }
            }
            socket.send_json(request)
            reply = socket.recv_json()
            print("Canais cadastrados:", json.dumps(reply, indent=2, ensure_ascii=False))
        case _:
            print("Opção não encontrada")

    opcao = input("Entre com a opção: ")
socket.close()
context.term()