import zmq
from datetime import datetime, timedelta, timezone

context = zmq.Context()
pub = context.socket(zmq.PUB)
pub.connect("tcp://proxy_pubsub:5557")

while True:
    print("Digite o tópico para publicar (nome do canal ou usuário):")
    topic = input().strip()
    print("Digite a mensagem a ser publicada:")
    msg = input().strip()
    time_br = datetime.now(timezone(timedelta(hours=-3))).strftime("%H:%M:%S")
    pub.send_string(f"{topic} {msg} [{time_br}]")
    print(f"Mensagem publicada em '{topic}': {msg} [{time_br}]")
    sair = input("Publicar outra mensagem? (s/n): ").strip().lower()
    if sair != 's':
        break

pub.close()
context.term()