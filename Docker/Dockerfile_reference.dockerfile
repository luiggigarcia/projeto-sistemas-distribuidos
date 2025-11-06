FROM python:3.13.7-alpine3.21

WORKDIR /app

RUN pip install pyzmq msgpack

COPY ./req-rep/reference.py ./reference.py

CMD ["python", "reference.py"]
