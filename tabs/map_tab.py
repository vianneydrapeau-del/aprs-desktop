from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolTip
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap
from PySide6.QtCore import Qt, QRectF, QRect, QPoint, QTimer
from urllib.request import Request, urlopen
from pathlib import Path
from datetime import datetime, timezone
import math

from db import get_stations_last_hours, get_stations_last_days


TILE_SIZE = 256
CACHE_DIR = Path.home() / "aprs-desktop" / "assets" / "tile_cache"


def latlon_to_world_pixels(lat, lon, zoom):
    scale = TILE_SIZE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * scale
    lat = max(min(lat, 85.05112878), -85.05112878)
    lat_rad = math.radians(lat)
    y = (
        (1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi)
        / 2.0
        * scale
    )
    return x, y


def world_pixels_to_tile(x, y):
    return int(x // TILE_SIZE), int(y // TILE_SIZE)


def parse_ts_utc(ts):
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class MapCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.points = []
        self.title = "Carte APRS"
        self.setMinimumSize(700, 500)

        self.tile_zoom = 8
        self.center_world_x = None
        self.center_world_y = None

        self.dragging = False
        self.last_mouse_pos = QPoint()

        self._view_rect = None
        self._screen_points = []

        self.setMouseTracking(True)

    def set_points(self, points, title="Carte APRS"):
        self.points = points
        self.title = title

        # On ne recentre pas à chaque refresh automatique
        if self.center_world_x is None or self.center_world_y is None:
            self.reset_view()
        else:
            self.update()

    def reset_view(self):
        if self.points:
            lats = [p["lat"] for p in self.points]
            lons = [p["lon"] for p in self.points]
            center_lat = (min(lats) + max(lats)) / 2.0
            center_lon = (min(lons) + max(lons)) / 2.0
        else:
            center_lat = 47.5
            center_lon = 7.5

        self.tile_zoom = 8
        self.center_world_x, self.center_world_y = latlon_to_world_pixels(center_lat, center_lon, self.tile_zoom)
        self.update()

    def _tile_path(self, z, x, y):
        return CACHE_DIR / "osm_standard" / str(z) / str(x) / f"{y}.png"

    def _get_tile_pixmap(self, z, x, y):
        max_tile = 2 ** z
        if x < 0 or y < 0 or x >= max_tile or y >= max_tile:
            return None

        tile_path = self._tile_path(z, x, y)
        tile_path.parent.mkdir(parents=True, exist_ok=True)

        if tile_path.exists():
            pm = QPixmap(str(tile_path))
            if not pm.isNull():
                return pm

        url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        req = Request(url, headers={"User-Agent": "APRSDesktop/1.0"})
        try:
            with urlopen(req, timeout=5) as resp:
                data = resp.read()
            tile_path.write_bytes(data)
            pm = QPixmap()
            pm.loadFromData(data)
            if not pm.isNull():
                return pm
        except Exception:
            return None

        return None

    def wheelEvent(self, event):
        old_zoom = self.tile_zoom

        if event.angleDelta().y() > 0:
            new_zoom = min(old_zoom + 1, 11)
        else:
            new_zoom = max(old_zoom - 1, 7)

        if new_zoom == old_zoom:
            return

        if self.center_world_x is None or self.center_world_y is None:
            self.tile_zoom = new_zoom
            self.update()
            return

        center_lon = (self.center_world_x / (TILE_SIZE * (2 ** old_zoom))) * 360.0 - 180.0
        n_old = math.pi - 2.0 * math.pi * self.center_world_y / (TILE_SIZE * (2 ** old_zoom))
        center_lat = math.degrees(math.atan(math.sinh(n_old)))

        self.tile_zoom = new_zoom
        self.center_world_x, self.center_world_y = latlon_to_world_pixels(center_lat, center_lon, new_zoom)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_mouse_pos = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        if self.dragging and self._view_rect is not None:
            delta = pos - self.last_mouse_pos
            self.last_mouse_pos = pos

            self.center_world_x -= delta.x()
            self.center_world_y -= delta.y()

            world_size = TILE_SIZE * (2 ** self.tile_zoom)
            self.center_world_x = max(0, min(self.center_world_x, world_size))
            self.center_world_y = max(0, min(self.center_world_y, world_size))

            self.update()
            return

        hovered = None
        for sp in self._screen_points:
            dx = pos.x() - sp["x"]
            dy = pos.y() - sp["y"]
            if (dx * dx + dy * dy) <= (8 * 8):
                hovered = sp
                break

        if hovered:
            QToolTip.showText(event.globalPosition().toPoint(), hovered["tooltip"], self)
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.unsetCursor()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.reset_view()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor("#f5f5f5"))

        margin = 10
        top_title_h = 22
        bottom_info_h = 18
        draw_rect = rect.adjusted(margin, top_title_h + 8, -margin, -bottom_info_h - 6)
        self._view_rect = draw_rect
        self._screen_points = []

        painter.setPen(QColor("#222222"))
        painter.setFont(QFont("Sans", 11, QFont.Bold))
        painter.drawText(10, 18, self.title)

        painter.setPen(QPen(QColor("#aaaaaa"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(draw_rect)

        if not self.points:
            painter.setFont(QFont("Sans", 12))
            painter.setPen(QColor("#333333"))
            painter.drawText(rect, Qt.AlignCenter, "Aucune station à afficher")
            return

        if self.center_world_x is None or self.center_world_y is None:
            self.reset_view()
            return

        half_w = draw_rect.width() / 2
        half_h = draw_rect.height() / 2

        tlx = self.center_world_x - half_w
        tly = self.center_world_y - half_h
        brx = self.center_world_x + half_w
        bry = self.center_world_y + half_h

        tx1, ty1 = world_pixels_to_tile(tlx, tly)
        tx2, ty2 = world_pixels_to_tile(brx, bry)

        painter.save()
        painter.setClipRect(draw_rect)

        for tx in range(tx1, tx2 + 1):
            for ty in range(ty1, ty2 + 1):
                pm = self._get_tile_pixmap(self.tile_zoom, tx, ty)

                tile_world_x = tx * TILE_SIZE
                tile_world_y = ty * TILE_SIZE

                px = draw_rect.left() + (tile_world_x - tlx)
                py = draw_rect.top() + (tile_world_y - tly)

                target = QRect(int(px), int(py), TILE_SIZE + 1, TILE_SIZE + 1)

                if pm is not None:
                    painter.drawPixmap(target, pm)
                else:
                    painter.fillRect(target, QColor("#e6e6e6"))
                    painter.setPen(QColor("#bbbbbb"))
                    painter.drawRect(target)

        painter.restore()

        painter.setPen(QPen(QColor(255, 255, 255, 170), 1))
        for i in range(1, 5):
            x = draw_rect.left() + i * draw_rect.width() / 5
            y = draw_rect.top() + i * draw_rect.height() / 5
            painter.drawLine(int(x), draw_rect.top(), int(x), draw_rect.bottom())
            painter.drawLine(draw_rect.left(), int(y), draw_rect.right(), int(y))

        now_utc = datetime.now(timezone.utc)
        painter.setFont(QFont("Sans", 8))

        for p in self.points:
            wx, wy = latlon_to_world_pixels(p["lat"], p["lon"], self.tile_zoom)
            x = draw_rect.left() + (wx - tlx)
            y = draw_rect.top() + (wy - tly)

            if x < draw_rect.left() - 20 or x > draw_rect.right() + 20 or y < draw_rect.top() - 20 or y > draw_rect.bottom() + 20:
                continue

            heard_dt = parse_ts_utc(p.get("last_ts"))
            heard_recent = False
            if heard_dt is not None:
                age_seconds = (now_utc - heard_dt).total_seconds()
                heard_recent = age_seconds <= 3600

            if heard_recent:
                point_color = QColor("#22c55e")
                outline_color = QColor("#15803d")
            else:
                point_color = QColor("#ef4444")
                outline_color = QColor("#b91c1c")

            painter.setPen(QPen(outline_color, 1))
            painter.setBrush(QBrush(point_color))
            painter.drawEllipse(QRectF(x - 5, y - 5, 10, 10))

            painter.setPen(QColor("#111111"))
            painter.drawText(int(x + 7), int(y - 7), p["name"])

            comment = p.get("comment") or "(pas de message)"
            last_ts = p.get("last_ts") or "inconnu"
            tooltip = f"{p['name']}\n{comment}\nDernière réception: {last_ts}"

            self._screen_points.append({
                "x": x,
                "y": y,
                "tooltip": tooltip,
            })

        painter.setPen(QColor("#333333"))
        painter.setFont(QFont("Sans", 8))
        info = (
            f"Stations: {len(self.points)}   "
            f"Zoom: {self.tile_zoom}   "
            f"Vert < 1h   "
            f"Rouge >= 1h"
        )
        painter.drawText(10, rect.height() - 8, info)


class MapTab(QWidget):
    def __init__(self, mode="6h"):
        super().__init__()
        self.mode = mode

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        top_bar = QHBoxLayout()
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_out = QPushButton("-")
        self.btn_reset = QPushButton("Recentrer")

        top_bar.addWidget(self.btn_zoom_in)
        top_bar.addWidget(self.btn_zoom_out)
        top_bar.addWidget(self.btn_reset)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.canvas = MapCanvas()
        layout.addWidget(self.canvas)

        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_reset.clicked.connect(self.canvas.reset_view)

        self.load_data()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_data)
        self.timer.start(10000)

    def zoom_in(self):
        self.canvas.tile_zoom = min(self.canvas.tile_zoom + 1, 11)
        self.canvas.update()

    def zoom_out(self):
        self.canvas.tile_zoom = max(self.canvas.tile_zoom - 1, 7)
        self.canvas.update()

    def _rows_to_points(self, rows):
        points = []

        for row in rows:
            name = row[0]
            last_ts = row[1]
            lat = row[2]
            lon = row[3]
            comment = row[5] if len(row) > 5 else ""

            if lat is None or lon is None:
                continue

            try:
                lat = float(lat)
                lon = float(lon)
            except Exception:
                continue

            points.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "last_ts": last_ts,
                "comment": comment or "",
            })

        return points

    def load_data(self):
        if self.mode == "6h":
            rows = get_stations_last_hours(6)
            points = self._rows_to_points(rows)
            self.canvas.set_points(points, "Carte APRS - 6 dernières heures")
        else:
            rows = get_stations_last_days(30)
            points = self._rows_to_points(rows)
            self.canvas.set_points(points, "Carte APRS - 30 derniers jours")
