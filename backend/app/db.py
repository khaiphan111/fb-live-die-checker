# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import sqlite3
import threading
import time
from typing import Optional

from . import config

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init_db() -> None:
    c = get_conn()
    with _lock:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS tg_users (
                tg_id        INTEGER PRIMARY KEY,
                username     TEXT,
                name         TEXT,
                balance      INTEGER DEFAULT 0,
                sub_until    INTEGER DEFAULT 0,
                created_at   INTEGER,
                is_blocked   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS watches (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id        INTEGER,
                uid          TEXT,
                note         TEXT,
                price        INTEGER DEFAULT 0,
                expire_at    INTEGER DEFAULT 0,
                last_status  TEXT,
                avatar_url   TEXT,
                last_checked INTEGER DEFAULT 0,
                active       INTEGER DEFAULT 1,
                created_at   INTEGER
            );

            CREATE TABLE IF NOT EXISTS logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        INTEGER,
                tg_id     INTEGER,
                uid       TEXT,
                kind      TEXT,
                message   TEXT
            );

            CREATE TABLE IF NOT EXISTS txns (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        INTEGER,
                tg_id     INTEGER,
                amount    INTEGER,
                reason    TEXT
            );
            """
        )
        for k, v in config.DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))
        c.commit()


def get_setting(key: str, default: str = "") -> str:
    row = get_conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _lock:
        c = get_conn()
        c.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        c.commit()


def all_settings() -> dict:
    rows = get_conn().execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def upsert_user(tg_id: int, username: str, name: str) -> sqlite3.Row:
    with _lock:
        c = get_conn()
        c.execute(
            "INSERT INTO tg_users(tg_id, username, name, created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username, name=excluded.name",
            (tg_id, username, name, int(time.time())),
        )
        c.commit()
    return get_user(tg_id)


def get_user(tg_id: int) -> Optional[sqlite3.Row]:
    return get_conn().execute("SELECT * FROM tg_users WHERE tg_id=?", (tg_id,)).fetchone()


def list_users() -> list:
    return get_conn().execute("SELECT * FROM tg_users ORDER BY created_at DESC").fetchall()


def adjust_balance(tg_id: int, amount: int, reason: str) -> None:
    with _lock:
        c = get_conn()
        c.execute("UPDATE tg_users SET balance = balance + ? WHERE tg_id=?", (amount, tg_id))
        c.execute(
            "INSERT INTO txns(ts, tg_id, amount, reason) VALUES(?,?,?,?)",
            (int(time.time()), tg_id, amount, reason),
        )
        c.commit()


def set_sub_until(tg_id: int, epoch: int) -> None:
    with _lock:
        c = get_conn()
        c.execute("UPDATE tg_users SET sub_until=? WHERE tg_id=?", (epoch, tg_id))
        c.commit()


def add_watch(tg_id: int, uid: str, note: str, price: int, expire_at: int) -> int:
    with _lock:
        c = get_conn()
        cur = c.execute(
            "INSERT INTO watches(tg_id, uid, note, price, expire_at, created_at, active) "
            "VALUES(?,?,?,?,?,?,1)",
            (tg_id, uid, note, price, expire_at, int(time.time())),
        )
        c.commit()
        return cur.lastrowid


def update_watch_status(watch_id: int, status: str, avatar_url: str) -> None:
    with _lock:
        c = get_conn()
        c.execute(
            "UPDATE watches SET last_status=?, avatar_url=?, last_checked=? WHERE id=?",
            (status, avatar_url, int(time.time()), watch_id),
        )
        c.commit()


def deactivate_watch(watch_id: int) -> None:
    with _lock:
        c = get_conn()
        c.execute("UPDATE watches SET active=0 WHERE id=?", (watch_id,))
        c.commit()


def remove_watch(tg_id: int, uid: str) -> int:
    with _lock:
        c = get_conn()
        cur = c.execute("DELETE FROM watches WHERE tg_id=? AND uid=?", (tg_id, uid))
        c.commit()
        return cur.rowcount


def user_watches(tg_id: int, only_active: bool = True) -> list:
    q = "SELECT * FROM watches WHERE tg_id=?"
    if only_active:
        q += " AND active=1"
    q += " ORDER BY created_at DESC"
    return get_conn().execute(q, (tg_id,)).fetchall()


def active_watches() -> list:
    return get_conn().execute("SELECT * FROM watches WHERE active=1").fetchall()


def all_watches() -> list:
    return get_conn().execute(
        "SELECT w.*, u.username, u.name FROM watches w "
        "LEFT JOIN tg_users u ON u.tg_id = w.tg_id ORDER BY w.created_at DESC"
    ).fetchall()


def add_log(kind: str, message: str, tg_id: int = 0, uid: str = "") -> None:
    with _lock:
        c = get_conn()
        c.execute(
            "INSERT INTO logs(ts, tg_id, uid, kind, message) VALUES(?,?,?,?,?)",
            (int(time.time()), tg_id, uid, kind, message),
        )
        c.commit()


def recent_logs(limit: int = 100) -> list:
    return get_conn().execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
