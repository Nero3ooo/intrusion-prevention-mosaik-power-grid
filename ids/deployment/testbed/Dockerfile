# syntax=docker/dockerfile:1.3

# Run with: DOCKER_BUILDKIT=1 docker build -t mosaik-testbed . && docker run -p8000:8000 mosaik-testbed

FROM python:3.9-slim-bullseye

RUN apt-get update && apt-get -y install \
    gcc \
    libhdf5-dev \
    libopenblas-dev \
    liblapack-dev

# upgrade pip
RUN /usr/local/bin/python -m pip install --upgrade pip

# Install mosaik-web
COPY mosaik-web /app/mosaik-web
WORKDIR /app/mosaik-web
RUN pip install -r requirements.txt
RUN python setup.py install

# Install mosaikpypower
COPY mosaikpypower /app/mosaikpypower
WORKDIR /app/mosaikpypower
RUN pip install -r requirements.txt
RUN python setup.py install


# Install Main app
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .

EXPOSE 10502 10503 8000
ENTRYPOINT [ "python", "test_scenario.py"]