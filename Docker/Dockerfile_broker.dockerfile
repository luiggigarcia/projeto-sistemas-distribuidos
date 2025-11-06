FROM python:3.13.7-alpine3.21

WORKDIR /app

RUN pip install pyzmq

# repo structure: repo root -> req-rep/broker.py
COPY ./req-rep/broker.py .

CMD ["python", "broker.py"]
