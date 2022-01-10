FROM python:3.9-slim

RUN apt-get update && \
    apt-get -y install --no-install-recommends build-essential

RUN /usr/local/bin/pip install --no-cache-dir \
    uvicorn[standard] \
    esg[standard]

EXPOSE 8080
WORKDIR /app
