FROM python:3.13.7-alpine3.21

WORKDIR /app

RUN pip install pyzmq

# copy proxy.py from repo root pub-sub folder
COPY ./pub-sub/proxy.py ./proxy.py

CMD ["python", "proxy.py"]
