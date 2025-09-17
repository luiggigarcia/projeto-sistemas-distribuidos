import os
import zmq

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://broker:5555")

opcao = input("Entre com a opção: ")
while opcao != "sair":
    match opcao:
        case "login":
            import time, json
            user = input("Nome de usuário: ")
            timestamp = time.time()
            request = {
                "service": "login",
                "data": {
                    "user": user,
                    "timestamp": timestamp
                }
            }
            socket.send_json(request)
            reply = socket.recv_json()
            print("Resposta do servidor:", json.dumps(reply, indent=2, ensure_ascii=False))
            print("Path: " + os.getcwd(), flush=True)

        case "users":
            import time, json
            request = {
                "service": "users",
                "data": {
                    "timestamp": time.time()
                }
            }
            socket.send_json(request)
            reply = socket.recv_json()
            print("Usuários cadastrados:", json.dumps(reply, indent=2, ensure_ascii=False))
        case _:
            print("Opção não encontrada")

    opcao = input("Entre com a opção: ")
socket.close()
context.term()