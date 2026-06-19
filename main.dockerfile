FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y git bash && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash agent && \
    mkdir -p /app/agent_workspace /app/memory

WORKDIR /app

RUN python3 -m venv /app/main_venv

COPY LineRun /app/LineRun
COPY src /app/src

RUN chown -R agent:agent /app

USER agent

RUN /app/main_venv/bin/pip install --no-cache-dir flask openai && \
    /app/main_venv/bin/pip install -e /app/LineRun

EXPOSE 5000

CMD ["/app/main_venv/bin/python", "src/main.py"]
