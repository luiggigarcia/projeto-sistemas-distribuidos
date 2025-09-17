import os
import zmq
import time, json

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.connect("tcp://broker:5556")

while True:
    request = socket.recv_json()

    if request["service"] == "login":
        dados = request["data"]
        user = dados.get("user")
        timestamp = dados.get("timestamp")
        status = "sucesso"
        description = ""

        # Validação dos dados do cliente
        if not user or not timestamp:
            status = "erro"
            description = "Dados de login inválidos: 'user' ou 'timestamp' ausente."
        else:
            print(f"Login recebido: user={user}, timestamp={timestamp}", flush=True)
            print("Path: " + os.getcwd(), flush=True)

            try:
                with open("/app/logins.txt", "a", encoding="utf-8") as f:
                    f.write(f"{user},{timestamp}\n")
            except Exception as e:
                status = "erro"
                description = f"Erro ao gravar arquivo: {str(e)}"

        reply = {
            "service": "login",
            "data": {
                "status": status,
                "timestamp": time.time(),
                "description": description
            }
        }
        socket.send_json(reply)
        continue

    if request["service"] == "users":
        dados = request["data"]
        req_timestamp = dados.get("timestamp")
        users = []
        try:
            with open("/app/logins.txt", "r", encoding="utf-8") as f:
                for line in f:
                    user = line.strip().split(",")[0]
                    if user:
                        users.append(user)
        except FileNotFoundError:
            users = []
        reply = {
            "service": "users",
            "data": {
                "timestamp": time.time(),
                "users": users
            }
        }
        socket.send_json(reply)
        continue