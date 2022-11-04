# syntax=docker/dockerfile:1.3

FROM python:3.9-slim-buster
WORKDIR /distributed-smart-grid-ids-main

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install tk-dev -y


COPY .. .
ENTRYPOINT [ "python3", "-u", "gui.py"]
