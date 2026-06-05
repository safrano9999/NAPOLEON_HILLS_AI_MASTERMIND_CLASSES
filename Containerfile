FROM quay.io/fedora/fedora:43

ENV PYTHONUNBUFFERED=1
WORKDIR /opt/safrano9999/NAPOLEON_HILLS_AI_MASTERMIND_CLASSES

RUN --mount=type=cache,target=/var/cache/dnf \
    dnf -y update && dnf -y install \
      bash \
      ca-certificates \
      python3 \
      python3-pip \
      python3-virtualenv \
      systemd \
    && dnf clean all

COPY requirements.txt /tmp/napoleon-requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m venv /opt/napoleon-venv \
 && /opt/napoleon-venv/bin/python -m pip install --upgrade pip \
 && /opt/napoleon-venv/bin/pip install -r /tmp/napoleon-requirements.txt \
 && printf '%s\n' \
      '#!/usr/bin/env bash' \
      'exec /opt/napoleon-venv/bin/uvicorn "$@"' \
      > /usr/local/bin/uvicorn \
 && chmod +x /usr/local/bin/uvicorn

COPY webui.py ./
COPY config.conf_example env.example ./
COPY config ./config
COPY functions ./functions
COPY members ./members
COPY members_ai ./members_ai
COPY PROMPT ./PROMPT
COPY sessions ./sessions
COPY static ./static
COPY services/*.service /etc/systemd/system/

RUN systemctl enable napoleon.service

EXPOSE 11004
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
