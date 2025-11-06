
import zmq

context = zmq.Context()

subscriber = context.socket(zmq.SUB)
subscriber.connect("tcp://proxy_pubsub:5558")

print("Digite o tópico para se inscrever (ex: seu nome ou canal):")
topic = input().strip()
subscriber.setsockopt_string(zmq.SUBSCRIBE, topic)
print(f"Inscrito no tópico: {topic}")

try:
    while True:
        msg = subscriber.recv_string()
        print(f"[RECEBIDO] {msg}")
except KeyboardInterrupt:
    print("\nSaindo...")
finally:
    subscriber.close()
    context.term()
