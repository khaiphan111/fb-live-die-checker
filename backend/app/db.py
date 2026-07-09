# FB Live/Die Checker — Tác giả: @nhanxp | Hỗ trợ: Telegram/Facebook nhanxp
import sqlite3
import threading
import time
import os
from typing import Optional

from . import config

try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

_lock = threading.Lock()
_conn = None
_is_postgres = False

def get_conn():
    global _conn, _is_postgres
    if _conn is None:
        if config.DATABASE_URL and HAS_POSTGRES:
            _conn = psycopg2.connect(config.DATABASE_URL)
            _conn.autocommit = True
            _is_postgres = True
        else:
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _is_postgres = False
    return _conn

def query(sql: str, params: tuple = ()):
    c = get_conn()
    if _is_postgres:
        sql = sql.replace("?", "%s")
        cur = c.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql, params)
        return cur
    else:
        return c.execute(sql, params)

def init_db() -> None:
    get_conn()
    with _lock:
        if _is_postgres:
            schema = """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS tg_users (
                tg_id        BIGINT PRIMARY KEY,
                username     TEXT,
                name         TEXT,
                balance      BIGINT DEFAULT 0,
                sub_until    BIGINT DEFAULT 0,
                created_at   BIGINT,
                is_blocked   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS watches (
                id           SERIAL PRIMARY KEY,
                tg_id        BIGINT,
                uid          TEXT,
                note         TEXT,
                price        BIGINT DEFAULT 0,
                expire_at    BIGINT DEFAULT 0,
                last_status  TEXT,
                avatar_url   TEXT,
                last_checked BIGINT DEFAULT 0,
                active       INTEGER DEFAULT 1,
                created_at   BIGINT
            );

            CREATE TABLE IF NOT EXISTS logs (
                id        SERIAL PRIMARY KEY,
                ts        BIGINT,
                tg_id     BIGINT,
                uid       TEXT,
                kind      TEXT,
                message   TEXT
            );

            CREATE TABLE IF NOT EXISTS txns (
                id        SERIAL PRIMARY KEY,
                ts        BIGINT,
                tg_id     BIGINT,
                amount    BIGINT,
                reason    TEXT
            );
            """
        else:
            schema = """
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
        if _is_postgres:
            cur = get_conn().cursor()
            cur.execute(schema)
        else:
            get_conn().executescript(schema)
            
        for k, v in config.DEFAULT_SETTINGS.items():
            query("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING", (k, v))
        if not _is_postgres:
            get_conn().commit()


def get_setting(key: str, default: str = "") -> str:
    row = query("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _lock:
        query(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
            (key, str(value)),
        )
        if not _is_postgres:
            get_conn().commit()


def all_settings() -> dict:
    rows = query("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def upsert_user(tg_id: int, username: str, name: str):
    with _lock:
        query(
            "INSERT INTO tg_users(tg_id, username, name, created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(tg_id) DO UPDATE SET username=EXCLUDED.username, name=EXCLUDED.name",
            (tg_id, username, name, int(time.time())),
        )
        if not _is_postgres:
            get_conn().commit()
    return get_user(tg_id)


def get_user(tg_id: int):
    return query("SELECT * FROM tg_users WHERE tg_id=?", (tg_id,)).fetchone()


def list_users() -> list:
    return query("SELECT * FROM tg_users ORDER BY created_at DESC").fetchall()


def adjust_balance(tg_id: int, amount: int, reason: str) -> None:
    with _lock:
        query("UPDATE tg_users SET balance = balance + ? WHERE tg_id=?", (amount, tg_id))
        query(
            "INSERT INTO txns(ts, tg_id, amount, reason) VALUES(?,?,?,?)",
            (int(time.time()), tg_id, amount, reason),
        )
        if not _is_postgres:
            get_conn().commit()


def set_sub_until(tg_id: int, epoch: int) -> None:
    with _lock:
        query("UPDATE tg_users SET sub_until=? WHERE tg_id=?", (epoch, tg_id))
        if not _is_postgres:
            get_conn().commit()


def add_watch(tg_id: int, uid: str, note: str, price: int, expire_at: int) -> int:
    with _lock:
        if _is_postgres:
            cur = query(
                "INSERT INTO watches(tg_id, uid, note, price, expire_at, created_at, active) "
                "VALUES(?,?,?,?,?,?,1) RETURNING id",
                (tg_id, uid, note, price, expire_at, int(time.time())),
            )
            return cur.fetchone()[0]
        else:
            cur = query(
                "INSERT INTO watches(tg_id, uid, note, price, expire_at, created_at, active) "
                "VALUES(?,?,?,?,?,?,1)",
                (tg_id, uid, note, price, expire_at, int(time.time())),
            )
            get_conn().commit()
            return cur.lastrowid


def update_watch_status(watch_id: int, status: str, avatar_url: str) -> None:
    with _lock:
        query(
            "UPDATE watches SET last_status=?, avatar_url=?, last_checked=? WHERE id=?",
            (status, avatar_url, int(time.time()), watch_id),
        )
        if not _is_postgres:
            get_conn().commit()


def deactivate_watch(watch_id: int) -> None:
    with _lock:
        query("UPDATE watches SET active=0 WHERE id=?", (watch_id,))
        if not _is_postgres:
            get_conn().commit()


def remove_watch(tg_id: int, uid: str) -> int:
    with _lock:
        cur = query("DELETE FROM watches WHERE tg_id=? AND uid=?", (tg_id, uid))
        if not _is_postgres:
            get_conn().commit()
        return cur.rowcount


def user_watches(tg_id: int, only_active: bool = True) -> list:
    q = "SELECT * FROM watches WHERE tg_id=?"
    if only_active:
        q += " AND active=1"
    q += " ORDER BY created_at DESC"
    return query(q, (tg_id,)).fetchall()


def active_watches() -> list:
    return query("SELECT * FROM watches WHERE active=1").fetchall()


def all_watches() -> list:
    return query(
        "SELECT w.*, u.username, u.name FROM watches w "
        "LEFT JOIN tg_users u ON u.tg_id = w.tg_id ORDER BY w.created_at DESC"
    ).fetchall()


def add_log(kind: str, message: str, tg_id: int = 0, uid: str = "") -> None:
    with _lock:
        query(
            "INSERT INTO logs(ts, tg_id, uid, kind, message) VALUES(?,?,?,?,?)",
            (int(time.time()), tg_id, uid, kind, message),
        )
        if not _is_postgres:
            get_conn().commit()


def recent_logs(limit: int = 100) -> list:
    return query("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
