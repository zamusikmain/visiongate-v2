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
# Колонки, добавленные для админ-панели (миграция существующей базы в init)
EXTRA_COLUMNS = {
    "source": "TEXT DEFAULT 'single'",   # single | batch | exam | import
    "batch_id": "TEXT",
    "summary_json": "TEXT",              # краткая сводка для списков/графиков (dashboard.summarize)
}
LIGHT_COLS = ("id, created_at, updated_at, imei, status, phase, fast_seconds, vlm_seconds, source, batch_id, "
              "summary_json, manual_status")


def _conn():
    ensure_dirs()
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.executescript(SCHEMA)
        have = {r[1] for r in c.execute("PRAGMA table_info(submissions)")}
        for col, ddl in EXTRA_COLUMNS.items():
            if col not in have:
                c.execute(f"ALTER TABLE submissions ADD COLUMN {col} {ddl}")
        c.execute("CREATE INDEX IF NOT EXISTS ix_created ON submissions(created_at)")
        # сводки для старых записей (один раз)
        from . import dashboard
        for sid, rj in c.execute("SELECT id, result_json FROM submissions "
                                 "WHERE summary_json IS NULL AND result_json IS NOT NULL").fetchall():
            try:
                c.execute("UPDATE submissions SET summary_json=? WHERE id=?",
                          (json.dumps(dashboard.summarize(json.loads(rj)), ensure_ascii=False), sid))
            except Exception:
                pass


def now():
    return datetime.now().isoformat(timespec="seconds")


def create(imei: str, client_barcode: str | None, source: str = "single", batch_id: str | None = None) -> int:
    with _lock, _conn() as c:
        cur = c.execute("INSERT INTO submissions(created_at, updated_at, imei, status, phase, client_barcode, source, "
                        "batch_id) VALUES (?,?,?,?,?,?,?,?)",
                        (now(), now(), imei, "PROCESSING", "fast", client_barcode, source, batch_id))
        return cur.lastrowid


def update(sid: int, **fields):
    if "result" in fields:
        from . import dashboard
        res = fields.pop("result")
        fields["result_json"] = json.dumps(res, ensure_ascii=False)
        fields["summary_json"] = json.dumps(dashboard.summarize(res), ensure_ascii=False)
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


def refresh_summaries() -> int:
    """Пересчитать сводки всех заявок (после изменения dashboard.summarize). Решения не меняются."""
    from . import dashboard
    with _lock, _conn() as c:
        rows = c.execute("SELECT id, result_json FROM submissions WHERE result_json IS NOT NULL").fetchall()
        for sid, rj in rows:
            try:
                c.execute("UPDATE submissions SET summary_json=? WHERE id=?",
                          (json.dumps(dashboard.summarize(json.loads(rj)), ensure_ascii=False), sid))
            except Exception:
                pass
    return len(rows)


def stats_rows() -> list[dict]:
    """Все заявки без тяжёлого result_json — для графиков и агрегатов."""
    with _conn() as c:
        rows = c.execute(f"SELECT {LIGHT_COLS} FROM submissions ORDER BY id").fetchall()
    return [_light(r) for r in rows]


def search(q: str = "", bucket: str = "", reason: str = "", source: str = "", date_from: str | None = None,
           date_to: str | None = None, limit: int = 50, offset: int = 0, ids_only: bool = False):
    """Фильтры списка заявок (только чтение). Возвращает (total, rows)."""
    where, args = [], []
    active = "phase IN ('vlm_pending','vlm_running')"
    if q:
        if q.isdigit() and len(q) <= 7:
            where.append("(id = ? OR imei LIKE ?)")
            args += [int(q), f"%{q}%"]
        else:
            where.append("imei LIKE ?")
            args.append(f"%{q}%")
    if bucket == "processing":
        where.append(f"({active} OR status='PROCESSING')")
    elif bucket in ("approved", "rejected"):
        where.append(f"status=? AND NOT {active}")
        args.append(bucket.upper())
    elif bucket == "review":
        where.append(f"status IN ('REVIEW','PRELIMINARY') AND NOT {active}")
    if reason:
        where.append("summary_json LIKE ?")
        args.append(f'%"{reason}"%')
    if source:
        where.append("COALESCE(source,'single')=?")
        args.append(source)
    if date_from:
        where.append("substr(created_at,1,10) >= ?")
        args.append(date_from)
    if date_to:
        where.append("substr(created_at,1,10) <= ?")
        args.append(date_to)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    with _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM submissions{w}", args).fetchone()[0]
        cols = "id" if ids_only else LIGHT_COLS
        rows = c.execute(f"SELECT {cols} FROM submissions{w} ORDER BY id DESC LIMIT ? OFFSET ?",
                         (*args, limit, offset)).fetchall()
    return total, ([r[0] for r in rows] if ids_only else [_light(r) for r in rows])


def _light(r) -> dict:
    d = dict(r)
    d["summary"] = json.loads(d.pop("summary_json", None) or "{}")
    d["source"] = d.get("source") or "single"
    return d


def _row(r, full=True) -> dict:
    d = dict(r)
    d.pop("summary_json", None)
    res = json.loads(d.pop("result_json") or "null")
    if full:
        d["result"] = res
    elif res:
        d["final"] = res.get("final")
    return d
