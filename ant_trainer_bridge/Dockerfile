# Pinned multi-arch index for python:3.12-slim-trixie.
FROM python:3.12-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

RUN apt-get update \
 && apt-get install -y --no-install-recommends libusb-1.0-0 ca-certificates \
 && apt-get dist-clean \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 10001 antbridge \
 && useradd --uid 10001 --gid antbridge --no-create-home --shell /usr/sbin/nologin antbridge

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY bridge.py /app/bridge.py
RUN python -m py_compile /app/bridge.py

COPY run.sh /run.sh
RUN chmod 0555 /run.sh \
 && chown -R antbridge:antbridge /app

# OpenANT's recommended udev rules set Garmin/Dynastream ANT USB devices to
# MODE=0666, so the long-running bridge does not need root.
USER 10001:10001

CMD ["/run.sh"]
