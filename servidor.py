import os
import zmq
import time, json
from datetime import datetime, timedelta, timezone

# Definir timezone de Brasília (UTC-3)
br_tz = timezone(timedelta(hours=-3))

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
        
        time_br = datetime.now(br_tz).strftime("%H:%M:%S")
        if not timestamp:
            timestamp = time_br

        if not user or not timestamp:
            status = "erro"
            description = "Dados de login inválidos: 'user' ou 'timestamp' ausente."

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
                "timestamp": time_br,
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
        time_br = datetime.now(br_tz).strftime("%H:%M:%S")
        reply = {
            "service": "users",
            "data": {
                "timestamp": time_br,
                "users": users
            }
        }
        socket.send_json(reply)
        continue

    if request["service"] == "channel":
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
                with open("/app/channels.txt", "a", encoding="utf-8") as f:
                    f.write(f"{channel},{timestamp}\n")
            except Exception as e:
                status = "erro"
                description = f"Erro ao gravar canal: {str(e)}"
        reply = {
            "service": "channel",
            "data": {
                "status": status,
                "timestamp": time_br,
                "description": description
            }
        }
        socket.send_json(reply)
        continue

    if request["service"] == "channels":
        dados = request["data"]
        req_timestamp = dados.get("timestamp")
        channels = []
        try:
            with open("/app/channels.txt", "r", encoding="utf-8") as f:
                for line in f:
                    channel = line.strip().split(",")[0]
                    if channel:
                        channels.append(channel)
        except FileNotFoundError:
            channels = []
        time_br = datetime.now(br_tz).strftime("%H:%M:%S")
        reply = {
            "service": "channels",
            "data": {
                "timestamp": time_br,
                "users": channels
            }
        }
        socket.send_json(reply)
        continue