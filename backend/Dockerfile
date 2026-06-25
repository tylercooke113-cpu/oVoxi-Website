FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    libsndfile1 \
    ffmpeg \
    libtbb12 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/lib/x86_64-linux-gnu/libtbb.so.12 /usr/lib/x86_64-linux-gnu/libtbb.so.2

RUN curl -L https://github.com/ai-mastering/phaselimiter/releases/download/v0.2.0/release.tar.xz \
    -o /tmp/release.tar.xz && \
    mkdir -p /tmp/pl && \
    cd /tmp/pl && \
    tar -xf /tmp/release.tar.xz && \
    mkdir -p /etc/phaselimiter && \
    cp -R phaselimiter/* /etc/phaselimiter/ && \
    cp phaselimiter/bin/phase_limiter /usr/local/bin/ && \
    chmod +x /usr/local/bin/phase_limiter && \
    rm -rf /tmp/pl /tmp/release.tar.xz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn server:app --host 0.0.0.0 --port $PORT
