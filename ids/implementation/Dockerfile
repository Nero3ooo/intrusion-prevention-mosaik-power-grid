# syntax=docker/dockerfile:1.3

FROM python:3.9-slim-buster
WORKDIR /ids

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY .. .