"""Запуск VisionGate для доступа через туннель (Cloudflare Quick Tunnel) — с паролем на вход.

То же приложение visiongate.web:app, обёрнутое в HTTP Basic Auth (основной код не меняется):
  python tools/serve_public.py --password <пароль> [--user samsung] [--port 8000]
Сервер слушает только 127.0.0.1: снаружи он доступен лишь через туннель (tunnel.ps1).

Что добавляет обёртка:
- логин/пароль на все страницы и API (браузер покажет стандартное окно входа);
- после 10 неверных попыток с одного адреса — блокировка на 15 минут;
- изменение настроек (POST /api/settings) запрещено: через туннель их не поменять
  (защита от включения внешнего API и подмены адреса Ollama). Настройки меняются локально.
"""
import argparse
import base64
import hmac
import logging
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

MAX_FAILS = 10
LOCK_SECONDS = 15 * 60
log = logging.getLogger("visiongate.public")


class BasicAuth:
    """Чистое ASGI-middleware: lifespan (запуск очереди, БД) проходит к приложению без изменений."""

    def __init__(self, app, user: str, password: str):
        self.app = app
        self.expected = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.fails: dict[str, list[float]] = {}

    async def _respond(self, send, status: int, body: str, extra=()):
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"), *extra]})
        await send({"type": "http.response.body", "body": body.encode()})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        # за туннелем все запросы приходят с 127.0.0.1; реальный адрес — в CF-Connecting-IP
        ip = headers.get(b"cf-connecting-ip", b"").decode() or (scope.get("client") or ("?",))[0]
        now = time.time()
        recent = [t for t in self.fails.get(ip, []) if now - t < LOCK_SECONDS]
        self.fails[ip] = recent
        if len(recent) >= MAX_FAILS:
            return await self._respond(send, 429, "Too many failed logins. Try again later.")
        auth = headers.get(b"authorization", b"").decode()
        given = auth[6:] if auth.lower().startswith("basic ") else ""
        if not hmac.compare_digest(given.encode(), self.expected.encode()):
            if given:
                recent.append(now)
                log.warning("failed login from %s (%d/%d)", ip, len(recent), MAX_FAILS)
            return await self._respond(send, 401, "Login required",
                                       [(b"www-authenticate", b'Basic realm="VisionGate", charset="UTF-8"')])
        if scope["path"] == "/api/settings" and scope["method"] != "GET":
            return await self._respond(send, 403, "Settings are read-only in public (tunnel) mode.")
        return await self.app(scope, receive, send)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=os.environ.get("VG_PUBLIC_USER", "samsung"))
    p.add_argument("--password", default=os.environ.get("VG_PUBLIC_PASSWORD", ""))
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    password = a.password or secrets.token_urlsafe(9)
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters")
    from visiongate.config import ensure_dirs
    from visiongate.web import app
    ensure_dirs()
    if not a.password:
        print(f"Generated password: {password}", flush=True)
    print(f"Public mode: login '{a.user}', listening on http://127.0.0.1:{a.port} (reach it via the tunnel)",
          flush=True)
    uvicorn.run(BasicAuth(app, a.user, password), host="127.0.0.1", port=a.port, workers=1)


if __name__ == "__main__":
    main()
