FROM python:3.13.7-alpine3.21

WORKDIR /app

RUN pip install pyzmq
RUN pip install msgpack

# repo root contains req-rep/servidor.py
COPY ./req-rep/servidor.py ./servidor.py
# copy admin helper so it's available inside /app of the server image
COPY ./req-rep/admin_tool.py ./admin_tool.py

CMD ["python", "servidor.py"]
