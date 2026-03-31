FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV NS3_VERSION=3.40
ENV NS3_DIR=/opt/ns3
ENV PYTHONPATH=/opt/wsn_framework:$PYTHONPATH

# ── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build python3 python3-pip python3-dev \
    git wget curl tar gzip \
    libgsl-dev libsqlite3-dev libxml2-dev libboost-all-dev \
    tcpdump wireshark-common \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

# ── NS-3 ─────────────────────────────────────────────────────────────────────
RUN mkdir -p $NS3_DIR && \
    wget -q https://www.nsnam.org/releases/ns-allinone-${NS3_VERSION}.tar.bz2 \
         -O /tmp/ns3.tar.bz2 && \
    tar -xjf /tmp/ns3.tar.bz2 -C $NS3_DIR --strip-components=1 && \
    rm /tmp/ns3.tar.bz2

WORKDIR $NS3_DIR
RUN ./ns3 configure --enable-python-bindings --enable-examples --enable-tests && \
    ./ns3 build -j$(nproc)

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# ── WSN Framework ─────────────────────────────────────────────────────────────
COPY . /opt/wsn_framework
RUN pip3 install --no-cache-dir -e /opt/wsn_framework

# ── Workspace ────────────────────────────────────────────────────────────────
RUN mkdir -p /workspace/results /workspace/configs /workspace/logs

WORKDIR /workspace
ENV NS3_PATH=$NS3_DIR

ENTRYPOINT ["python3", "-m", "wsn_framework.cli"]
CMD ["--help"]
