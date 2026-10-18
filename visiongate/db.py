"""SQLite: заявки, результаты проверки, ручные решения."""
import json
import sqlite3
import threading
from datetime import datetime

from .config import DB_PATH, ensure_dirs

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    imei TEXT NOT NULL,
    status TEXT NOT NULL,            -- PROCESSING | PRELIMINARY | APPROVED | REJECTED | REVIEW
    phase TEXT NOT NULL,             -- fast | vlm_pending | vlm_running | final
    device_file TEXT, scan_file TEXT,
    client_barcode TEXT,             -- IMEI, считанный камерой в браузере (подсказка, не доказательство)
    result_json TEXT,
    fast_seconds REAL, vlm_seconds REAL,
    manual_status TEXT, manual_reason TEXT, manual_comment TEXT, reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_status ON submissions(status);
"""


def _conn():
    ensure_dirs()
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.executescript(SCHEMA)


def now():
    return datetime.now().isoformat(timespec="seconds")


def create(imei: str, client_barcode: str | None) -> int:
    with _lock, _conn() as c:
        cur = c.execute("INSERT INTO submissions(created_at, updated_at, imei, status, phase, client_barcode) "
                        "VALUES (?,?,?,?,?,?)", (now(), now(), imei, "PROCESSING", "fast", client_barcode))
        return cur.lastrowid


def update(sid: int, **fields):
    if "result" in fields:
        fields["result_json"] = json.dumps(fields.pop("result"), ensure_ascii=False)
    fields["updated_at"] = now()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE submissions SET {cols} WHERE id=?", (*fields.values(), sid))


def get(sid: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
    return _row(r) if r else None


def list_(status: str | None = None, limit: int = 200) -> list[dict]:
    q, args = "SELECT * FROM submissions", []
    if status == "TODO":  # всё, что ждёт человека
        q += " WHERE status='REVIEW' AND manual_status IS NULL"
    elif status:
        q += " WHERE status=?"
        args.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    return [_row(r, full=False) for r in rows]


def pending_vlm() -> list[int]:
    with _conn() as c:
        return [r[0] for r in c.execute("SELECT id FROM submissions WHERE phase IN ('vlm_pending','vlm_running') "
                                        "ORDER BY id")]


def _row(r, full=True) -> dict:
    d = dict(r)
    res = json.loads(d.pop("result_json") or "null")
    if full:
        d["result"] = res
    elif res:
        d["final"] = res.get("final")
    return d
