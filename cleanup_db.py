#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path.home() / "aprs-desktop" / "aprs_desktop.db"

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM packets")
    before_packets = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM stations")
    before_stations = cur.fetchone()[0]

    cur.execute("DELETE FROM packets WHERE ts < datetime('now','-30 days')")
    deleted_packets = cur.rowcount if cur.rowcount != -1 else 0

    cur.execute("DELETE FROM stations WHERE last_ts < datetime('now','-30 days')")
    deleted_stations = cur.rowcount if cur.rowcount != -1 else 0

    conn.commit()
    cur.execute("VACUUM")

    cur.execute("SELECT COUNT(*) FROM packets")
    after_packets = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM stations")
    after_stations = cur.fetchone()[0]

    conn.close()

    print(f"Packets:  {before_packets} -> {after_packets} (supprimés: {deleted_packets})")
    print(f"Stations: {before_stations} -> {after_stations} (supprimés: {deleted_stations})")

if __name__ == '__main__':
    main()
