"""Запуск: python -m visiongate [--http] [--host 0.0.0.0] [--port 8443]"""
import argparse
import logging

import uvicorn

from .config import CERT_DIR, ensure_dirs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--http", action="store_true", help="plain HTTP (the phone camera will not work)")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ensure_dirs()
    kw = {}
    if not a.http:
        from .certs import ensure_cert
        cert, key = ensure_cert(CERT_DIR)
        kw = {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
    port = a.port or (8000 if a.http else 8443)
    uvicorn.run("visiongate.web:app", host=a.host, port=port, workers=1, **kw)


if __name__ == "__main__":
    main()
