FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ \
        libpgf-dev \
        python3 \
        python3-pil \
        findimagedupes \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY export.py dedup.py pgf2ppm.cpp ./

RUN g++ -O2 -I/usr/include/libpgf -o /app/pgf2ppm /app/pgf2ppm.cpp -lpgf
