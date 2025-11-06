import zmq

context = zmq.Context()

# XSUB socket para publishers
xsub = context.socket(zmq.XSUB)
xsub.bind("tcp://*:5557")

# XPUB socket para subscribers
xpub = context.socket(zmq.XPUB)
xpub.bind("tcp://*:5558")

print("[proxy_pubsub] Proxy Pub/Sub rodando nas portas 5557 (XSUB) e 5558 (XPUB)...")
zmq.proxy(xsub, xpub)

xsub.close()
xpub.close()
context.term()
