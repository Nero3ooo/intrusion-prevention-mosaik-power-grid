# syntax=docker/dockerfile:1.3

# Run with: DOCKER_BUILDKIT=1 docker build -t mosaik-ids . && docker run mosaik-ids

FROM python:3.7-slim-buster
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080
ENTRYPOINT [ "python3", "-u", "webserver.py"]