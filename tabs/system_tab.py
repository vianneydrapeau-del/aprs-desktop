from math import radians, sin, cos, sqrt, atan2

from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFormLayout,
    QGroupBox, QTextEdit, QPushButton, QMessageBox, QHBoxLayout
)

from services.system_stats import get_stats
from config import MY_CALLSIGN, DEFAULT_MAP_LAT, DEFAULT_MAP_LON
from db import get_db


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def get_aprs_summary():
    summary = {
        "stations_1h": 0,
        "stations_24h": 0,
        "farthest_callsign": "-",
        "farthest_distance_km": 0.0,
        "hourly_labels": [],
        "hourly_values": [],
    }

    with get_db() as conn:
        cur = conn.execute(
            """
            SELECT COUNT(*)
            FROM stations
            WHERE datetime(last_ts) >= datetime('now', '-1 hour')
            """
        )
        summary["stations_1h"] = cur.fetchone()[0] or 0

        cur = conn.execute(
            """
            SELECT COUNT(*)
            FROM stations
            WHERE datetime(last_ts) >= datetime('now', '-24 hours')
            """
        )
        summary["stations_24h"] = cur.fetchone()[0] or 0

        cur = conn.execute(
            """
            SELECT callsign, latitude, longitude
            FROM stations
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND datetime(last_ts) >= datetime('now', '-30 days')
            """
        )
        rows = cur.fetchall()

        farthest_name = "-"
        farthest_km = 0.0

        for callsign, lat, lon in rows:
            try:
                lat = float(lat)
                lon = float(lon)
            except Exception:
                continue

            dist = haversine_km(DEFAULT_MAP_LAT, DEFAULT_MAP_LON, lat, lon)
            if dist > farthest_km:
                farthest_km = dist
                farthest_name = callsign

        summary["farthest_callsign"] = farthest_name
        summary["farthest_distance_km"] = farthest_km

        cur = conn.execute(
            """
            SELECT
                strftime('%H:00', datetime(last_ts, 'localtime')) AS hour_slot,
                COUNT(*)
            FROM stations
            WHERE datetime(last_ts) >= datetime('now', '-24 hours')
            GROUP BY hour_slot
            ORDER BY hour_slot
            """
        )
        graph_rows = cur.fetchall()

    hour_map = {hour: count for hour, count in graph_rows}

    labels = []
    values = []

    from datetime import datetime, timedelta
    now = datetime.now()

    for i in range(23, -1, -1):
        h = now - timedelta(hours=i)
        label = h.strftime("%H:00")
        labels.append(label)
        values.append(hour_map.get(label, 0))

    summary["hourly_labels"] = labels
    summary["hourly_values"] = values

    return summary


class SimpleBarGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.labels = []
        self.values = []
        self.setMinimumHeight(220)

    def set_data(self, labels, values):
        self.labels = labels
        self.values = values
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor("#fafafa"))

        margin_left = 40
        margin_right = 15
        margin_top = 20
        margin_bottom = 40

        plot = rect.adjusted(margin_left, margin_top, -margin_right, -margin_bottom)

        painter.setPen(QPen(QColor("#cfcfcf"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(plot)

        if not self.values:
            painter.setPen(QColor("#333333"))
            painter.drawText(rect, Qt.AlignCenter, "Pas encore de données")
            return

        max_val = max(self.values)
        if max_val < 1:
            max_val = 1

        # grille horizontale
        painter.setPen(QPen(QColor("#e5e5e5"), 1, Qt.DashLine))
        for i in range(5):
            y = plot.bottom() - (i * plot.height() / 4)
            painter.drawLine(plot.left(), int(y), plot.right(), int(y))

        count = len(self.values)
        slot_w = plot.width() / max(count, 1)
        bar_w = max(slot_w * 0.65, 4)

        painter.setFont(QFont("Sans", 8))

        for idx, value in enumerate(self.values):
            x = plot.left() + idx * slot_w + (slot_w - bar_w) / 2
            h = (value / max_val) * (plot.height() - 10)
            y = plot.bottom() - h

            painter.setPen(QPen(QColor("#2563eb"), 1))
            painter.setBrush(QBrush(QColor("#60a5fa")))
            painter.drawRect(QRectF(x, y, bar_w, h))

            # toutes les 3 heures pour éviter surcharge
            if idx % 3 == 0:
                painter.setPen(QColor("#333333"))
                painter.drawText(
                    QRectF(x - 10, plot.bottom() + 4, slot_w + 20, 18),
                    Qt.AlignHCenter | Qt.AlignTop,
                    self.labels[idx][:2]
                )

        # échelle gauche
        painter.setPen(QColor("#333333"))
        painter.drawText(5, plot.top() + 5, str(max_val))
        painter.drawText(10, plot.bottom(), "0")

        painter.setFont(QFont("Sans", 9, QFont.Bold))
        painter.drawText(10, 14, "Stations entendues / heure (24h)")


class SystemTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # ----- PARTIE SYSTEME -----
        group = QGroupBox("État du Raspberry Pi")
        form = QFormLayout(group)

        self.lbl_host = QLabel("-")
        self.lbl_cpu = QLabel("-")
        self.lbl_mem = QLabel("-")
        self.lbl_disk = QLabel("-")
        self.lbl_temp = QLabel("-")

        form.addRow("Nom machine :", self.lbl_host)
        form.addRow("CPU % :", self.lbl_cpu)
        form.addRow("RAM % :", self.lbl_mem)
        form.addRow("Disque % :", self.lbl_disk)
        form.addRow("Température CPU :", self.lbl_temp)

        layout.addWidget(group)

        # ----- PARTIE STATISTIQUES APRS -----
        aprs_group = QGroupBox("Statistiques APRS")
        aprs_form = QFormLayout(aprs_group)

        self.lbl_stations_1h = QLabel("-")
        self.lbl_stations_24h = QLabel("-")
        self.lbl_far_callsign = QLabel("-")
        self.lbl_far_distance = QLabel("-")

        aprs_form.addRow("Stations entendues (1h) :", self.lbl_stations_1h)
        aprs_form.addRow("Stations entendues (24h) :", self.lbl_stations_24h)
        aprs_form.addRow("Station la plus lointaine :", self.lbl_far_callsign)
        aprs_form.addRow("Distance max :", self.lbl_far_distance)

        layout.addWidget(aprs_group)

        # ----- GRAPHIQUE -----
        graph_group = QGroupBox("Graphique APRS")
        graph_layout = QVBoxLayout(graph_group)
        self.graph = SimpleBarGraph()
        graph_layout.addWidget(self.graph)
        layout.addWidget(graph_group)

        # ----- PARTIE ENVOI APRS -----
        send_group = QGroupBox("Envoyer un message APRS")
        send_layout = QVBoxLayout(send_group)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Tape ton message APRS ici...")

        btn_row = QHBoxLayout()
        self.btn_send = QPushButton("Générer paquet APRS")
        self.btn_send.clicked.connect(self.send_aprs)
        btn_row.addWidget(self.btn_send)
        btn_row.addStretch()

        send_layout.addWidget(self.text_edit)
        send_layout.addLayout(btn_row)

        layout.addWidget(send_group)
        layout.addStretch()

        # ----- TIMER -----
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start(10000)

        self.refresh_all()

    def refresh_all(self):
        self.refresh_stats()
        self.refresh_aprs_stats()

    def refresh_stats(self):
        s = get_stats()

        self.lbl_host.setText(str(s["hostname"]))
        self.lbl_cpu.setText(f'{s["cpu_percent"]} %')
        self.lbl_mem.setText(f'{s["mem_percent"]} %')
        self.lbl_disk.setText(f'{s["disk_percent"]} %')

        if s["cpu_temp"] is None:
            self.lbl_temp.setText("indisponible")
        else:
            self.lbl_temp.setText(f'{s["cpu_temp"]} °C')

    def refresh_aprs_stats(self):
        s = get_aprs_summary()

        self.lbl_stations_1h.setText(str(s["stations_1h"]))
        self.lbl_stations_24h.setText(str(s["stations_24h"]))
        self.lbl_far_callsign.setText(str(s["farthest_callsign"]))
        self.lbl_far_distance.setText(f'{s["farthest_distance_km"]:.1f} km')

        self.graph.set_data(s["hourly_labels"], s["hourly_values"])

    def send_aprs(self):
        text = self.text_edit.toPlainText().strip()

        if not text:
            QMessageBox.warning(self, "Erreur", "Message vide")
            return

        packet = f"{MY_CALLSIGN}>APRS:>{text}"

        QMessageBox.information(
            self,
            "Paquet APRS généré",
            f"{packet}"
        )
