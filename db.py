import sqlite3
from contextlib import contextmanager
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    raw TEXT NOT NULL,
    source TEXT,
    heard TEXT,
    level TEXT,
    error TEXT,
    dti TEXT,
    name TEXT,
    symbol TEXT,
    latitude REAL,
    longitude REAL,
    speed TEXT,
    course TEXT,
    altitude TEXT,
    frequency TEXT,
    offset TEXT,
    tone TEXT,
    system TEXT,
    status TEXT,
    telemetry TEXT,
    comment TEXT
);

CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    callsign TEXT NOT NULL UNIQUE,
    last_ts TEXT NOT NULL,
    last_raw TEXT,
    latitude REAL,
    longitude REAL,
    symbol TEXT,
    comment TEXT
);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)


def insert_packet(
    ts,
    raw,
    source=None,
    heard=None,
    level=None,
    error=None,
    dti=None,
    name=None,
    symbol=None,
    latitude=None,
    longitude=None,
    speed=None,
    course=None,
    altitude=None,
    frequency=None,
    offset=None,
    tone=None,
    system=None,
    status=None,
    telemetry=None,
    comment=None,
):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO packets (
                ts, raw, source, heard, level, error, dti, name, symbol,
                latitude, longitude, speed, course, altitude, frequency,
                offset, tone, system, status, telemetry, comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts, raw, source, heard, level, error, dti, name, symbol,
                latitude, longitude, speed, course, altitude, frequency,
                offset, tone, system, status, telemetry, comment
            ),
        )


def upsert_station(
    callsign,
    last_ts,
    last_raw=None,
    latitude=None,
    longitude=None,
    symbol=None,
    comment=None,
):
    with get_db() as conn:
        cur = conn.execute(
            "SELECT id FROM stations WHERE callsign = ?",
            (callsign,),
        )
        row = cur.fetchone()

        if row:
            conn.execute(
                """
                UPDATE stations
                SET last_ts = ?, last_raw = ?, latitude = ?, longitude = ?, symbol = ?, comment = ?
                WHERE callsign = ?
                """,
                (last_ts, last_raw, latitude, longitude, symbol, comment, callsign),
            )
        else:
            conn.execute(
                """
                INSERT INTO stations (callsign, last_ts, last_raw, latitude, longitude, symbol, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (callsign, last_ts, last_raw, latitude, longitude, symbol, comment),
            )


def get_recent_packets(limit=200):
    with get_db() as conn:
        cur = conn.execute(
            """
            SELECT ts, source, heard, latitude, longitude, comment, raw
            FROM packets
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def get_stations_last_hours(hours=6):
    with get_db() as conn:
        cur = conn.execute(
            """
            SELECT callsign, last_ts, latitude, longitude, symbol, comment, last_raw
            FROM stations
            WHERE datetime(last_ts) >= datetime('now', ?)
            ORDER BY last_ts DESC
            """,
            (f"-{hours} hours",),
        )
        return cur.fetchall()


def get_stations_last_days(days=30):
    with get_db() as conn:
        cur = conn.execute(
            """
            SELECT callsign, last_ts, latitude, longitude, symbol, comment, last_raw
            FROM stations
            WHERE datetime(last_ts) >= datetime('now', ?)
            ORDER BY last_ts DESC
            """,
            (f"-{days} days",),
        )
        return cur.fetchall()


def purge_old_packets(days=30):
    with get_db() as conn:
        conn.execute(
            """
            DELETE FROM packets
            WHERE datetime(ts) < datetime('now', ?)
            """,
            (f"-{days} days",),
        )
