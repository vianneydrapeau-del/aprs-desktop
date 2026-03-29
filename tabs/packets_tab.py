from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from datetime import datetime
import os
import csv
import io

from db import insert_packet, upsert_station


class PacketsTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text.setFont(QFont("Monospace", 10))
        layout.addWidget(self.text)

        self.log_file = ""
        self.last_size = 0
        self.current_day = ""

        self.update_log_file(force=True)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_new_lines)
        self.timer.start(1000)

        self.text.append(f"Lecture du log : {self.log_file}\n")

    def refresh(self):
        self.read_new_lines()

    def update_log_file(self, force=False):
        today = datetime.now().strftime("%Y-%m-%d")
        new_file = f"/tmp/direwolf.log/{today}.log"

        if force or new_file != self.log_file:
            self.log_file = new_file
            self.current_day = today
            self.last_size = 0

            if force:
                self.text.append(f"Log du jour : {self.log_file}\n")
            else:
                self.text.append("")
                self.text.append("============================================================")
                self.text.append(f"Nouveau jour détecté -> bascule log : {self.log_file}")
                self.text.append("============================================================")
                self.text.append("")

            if not os.path.exists(self.log_file):
                self.text.append(f"En attente du fichier : {self.log_file}")

    def save_csv_line_to_db(self, line: str):
        try:
            reader = csv.reader(io.StringIO(line))
            row = next(reader)

            if len(row) < 22:
                return

            if row[0] == "chan":
                return

            ts = row[2].strip()
            source = row[3].strip()
            heard = row[4].strip()
            level = row[5].strip()
            error = row[6].strip()
            dti = row[7].strip()
            name = row[8].strip()
            symbol = row[9].strip()

            latitude = row[10].strip()
            longitude = row[11].strip()

            speed = row[12].strip()
            course = row[13].strip()
            altitude = row[14].strip()
            frequency = row[15].strip()
            offset = row[16].strip()
            tone = row[17].strip()
            system = row[18].strip()
            status = row[19].strip()
            telemetry = row[20].strip()
            comment = row[21].strip()

            try:
                latitude = float(latitude) if latitude else None
            except Exception:
                latitude = None

            try:
                longitude = float(longitude) if longitude else None
            except Exception:
                longitude = None

            insert_packet(
                ts=ts,
                raw=line,
                source=source or None,
                heard=heard or None,
                level=level or None,
                error=error or None,
                dti=dti or None,
                name=name or None,
                symbol=symbol or None,
                latitude=latitude,
                longitude=longitude,
                speed=speed or None,
                course=course or None,
                altitude=altitude or None,
                frequency=frequency or None,
                offset=offset or None,
                tone=tone or None,
                system=system or None,
                status=status or None,
                telemetry=telemetry or None,
                comment=comment or None,
            )

            if source:
                upsert_station(
                    callsign=source,
                    last_ts=ts,
                    last_raw=line,
                    latitude=latitude,
                    longitude=longitude,
                    symbol=symbol or None,
                    comment=comment or None,
                )

        except Exception as e:
            self.text.append(f"Erreur SQLite/CSV: {e}")

    def format_csv_line(self, line: str) -> str:
        try:
            reader = csv.reader(io.StringIO(line))
            row = next(reader)

            if len(row) < 6:
                return line

            labels = [
                "chan",
                "utime",
                "isotime",
                "source",
                "heard",
                "level",
                "error",
                "dti",
                "name",
                "symbol",
                "latitude",
                "longitude",
                "speed",
                "course",
                "altitude",
                "frequency",
                "offset",
                "tone",
                "system",
                "status",
                "telemetry",
                "comment",
            ]

            if row[0] == "chan":
                return "=== ENTÊTE CSV DIRE WOLF ===\n" + "\n".join(
                    f"{i+1:02d}. {value}" for i, value in enumerate(row)
                )

            data = {}
            for i, value in enumerate(row):
                key = labels[i] if i < len(labels) else f"col_{i}"
                data[key] = value

            lines = []
            lines.append("------------------------------------------------------------")
            lines.append("TRAME CSV DIRE WOLF")
            lines.append(f"Heure ISO   : {data.get('isotime', '')}")
            lines.append(f"Source      : {data.get('source', '')}")
            lines.append(f"Entendu par : {data.get('heard', '')}")
            lines.append(f"Niveau      : {data.get('level', '')}")
            lines.append(f"Erreur      : {data.get('error', '')}")
            lines.append(f"DTI         : {data.get('dti', '')}")
            lines.append(f"Nom         : {data.get('name', '')}")
            lines.append(f"Symbole     : {data.get('symbol', '')}")
            lines.append(f"Latitude    : {data.get('latitude', '')}")
            lines.append(f"Longitude   : {data.get('longitude', '')}")
            lines.append(f"Vitesse     : {data.get('speed', '')}")
            lines.append(f"Cap         : {data.get('course', '')}")
            lines.append(f"Altitude    : {data.get('altitude', '')}")
            lines.append(f"Fréquence   : {data.get('frequency', '')}")
            lines.append(f"Offset      : {data.get('offset', '')}")
            lines.append(f"Tonalité    : {data.get('tone', '')}")
            lines.append(f"Système     : {data.get('system', '')}")
            lines.append(f"Statut      : {data.get('status', '')}")
            lines.append(f"Télémétrie  : {data.get('telemetry', '')}")
            lines.append(f"Commentaire : {data.get('comment', '')}")
            lines.append("")
            lines.append("LIGNE BRUTE :")
            lines.append(line)

            return "\n".join(lines)

        except Exception:
            return line

    def read_new_lines(self):
        self.update_log_file()

        if not os.path.exists(self.log_file):
            return

        try:
            current_size = os.path.getsize(self.log_file)

            if current_size < self.last_size:
                self.last_size = 0

            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self.last_size)
                new_data = f.read()
                self.last_size = f.tell()

            if not new_data.strip():
                return

            for line in new_data.splitlines():
                line = line.rstrip()
                if not line:
                    continue

                if "," in line:
                    self.save_csv_line_to_db(line)
                    self.text.append(self.format_csv_line(line))
                    self.text.append("")
                else:
                    if "Weather" in line or "WX" in line:
                        self.text.append("WX: " + line)
                    else:
                        self.text.append(line)

        except Exception as e:
            self.text.append(f"Erreur lecture log: {e}")
