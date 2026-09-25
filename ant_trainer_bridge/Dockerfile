FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends libusb-1.0-0 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bridge.py /app/bridge.py
RUN python -m py_compile /app/bridge.py

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
