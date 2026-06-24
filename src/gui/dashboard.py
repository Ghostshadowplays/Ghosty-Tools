import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QGridLayout, QProgressBar)
from PyQt6.QtCore import Qt, QRectF, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QConicalGradient

class NavButton(QPushButton):
    def __init__(self, title, subtitle="", icon_text="", count=None, parent=None):
        super().__init__(parent)
        self._title = title
        self.setCheckable(True)
        self.setFixedHeight(65)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # Icon label
        self.icon_label = QLabel(icon_text)
        self.icon_label.setFixedWidth(30)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Use Segoe MDL2 Assets for cleaner icons on Windows
        if sys.platform == "win32":
            self.icon_label.setFont(QFont("Segoe MDL2 Assets", 15))
        else:
            self.icon_label.setFont(QFont("Segoe UI", 15))

        self.icon_label.setStyleSheet("color: #888; background: transparent;")
        layout.addWidget(self.icon_label)
        
        # Text container
        text_container = QVBoxLayout()
        text_container.setSpacing(2)
        
        # Title & Count
        title_layout = QHBoxLayout()
        title_layout.setSpacing(5)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #d4d4d4; background: transparent;")
        title_layout.addWidget(self.title_label)
        
        if count is not None:
            self.count_label = QLabel(f"({count})")
            self.count_label.setStyleSheet("font-size: 12px; color: #666; background: transparent;")
            title_layout.addWidget(self.count_label)
            
        title_layout.addStretch()
        text_container.addLayout(title_layout)
        
        # Subtitle
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setStyleSheet("font-size: 11px; color: #666; background: transparent;")
            text_container.addWidget(self.subtitle_label)
            
        layout.addLayout(text_container)
        
        # Chevron
        self.chevron_label = QLabel("›")
        self.chevron_label.setStyleSheet("font-size: 18px; color: #444; background: transparent;")
        layout.addWidget(self.chevron_label)
        
        self.update_style()
        self.toggled.connect(self.update_style)

    def text(self):
        return self._title

    def update_style(self):
        if self.isChecked():
            self.setStyleSheet("""
                NavButton {
                    background-color: #25252b;
                    border-radius: 8px;
                    border: none;
                }
            """)
            self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: white; background: transparent;")
            self.icon_label.setStyleSheet("color: #4158D0; background: transparent;")
            self.chevron_label.setStyleSheet("font-size: 18px; color: #4158D0; background: transparent;")
        else:
            self.setStyleSheet("""
                NavButton {
                    background-color: transparent;
                    border-radius: 8px;
                    border: none;
                }
                NavButton:hover {
                    background-color: #1e1e24;
                }
            """)
            self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #d4d4d4; background: transparent;")
            self.icon_label.setStyleSheet("color: #888; background: transparent;")
            self.chevron_label.setStyleSheet("font-size: 18px; color: #444; background: transparent;")

class CircularProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 90
        self._status = "Good"
        self.setFixedSize(120, 120)
        self._color = QColor("#00ff88")

    @pyqtProperty(int)
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        self.update()

    @pyqtProperty(str)
    def status(self):
        return self._status

    @status.setter
    def status(self, val):
        self._status = val
        self.update()

    def paintEvent(self, event):
        width = self.width()
        height = self.height()
        thickness = 10
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(thickness/2, thickness/2, width - thickness, height - thickness)
        
        # Draw background circle
        painter.setPen(QPen(QColor("#2a2a2a"), thickness, Qt.PenStyle.SolidLine))
        painter.drawEllipse(rect)
        
        # Draw value arc
        painter.setPen(QPen(self._color, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span_angle = -int(self._value * 3.6 * 16)
        painter.drawArc(rect, 90 * 16, span_angle)
        
        # Draw Score
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        score_rect = QRectF(0, height/2 - 25, width, 30)
        painter.drawText(score_rect, Qt.AlignmentFlag.AlignCenter, str(self._value))
        
        # Draw Status
        painter.setPen(QPen(QColor("#888")))
        painter.setFont(QFont("Segoe UI", 10))
        status_rect = QRectF(0, height/2 + 5, width, 20)
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, self._status)

class PageHeader(QWidget):
    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 10)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        self.layout.addWidget(self.title_label)
        
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setStyleSheet("color: #888; font-size: 12px;")
            self.layout.addWidget(self.subtitle_label)

class DashboardCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardCard")
        self.setStyleSheet("""
            QFrame#DashboardCard {
                background-color: #1a1a1f;
                border: 1px solid #333;
                border-radius: 10px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        if title:
            self.title_label = QLabel(title.upper())
            self.title_label.setStyleSheet("color: #666; font-size: 10px; font-weight: bold;")
            self.layout.addWidget(self.title_label)

class MonitorCard(DashboardCard):
    def __init__(self, title, color="#4158D0", parent=None):
        super().__init__(title, parent)
        self.value_label = QLabel("0%")
        self.value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        self.layout.addWidget(self.value_label)
        
        self.details_label = QLabel("...")
        self.details_label.setStyleSheet("color: #888; font-size: 11px;")
        self.layout.addWidget(self.details_label)
        
        self.bar = QProgressBar()
        self.bar.setFixedHeight(4)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #2a2a2a; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {color}; border-radius: 2px; }}
        """)
        self.layout.addWidget(self.bar)

class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 20, 30, 20)
        self.layout.setSpacing(20)
        
        # Top Bar
        top_layout = QHBoxLayout()
        title_info = QVBoxLayout()
        self.title_label = QLabel("Dashboard")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        title_info.addWidget(self.title_label)
        
        self.os_label = QLabel("Microsoft Windows 11 Pro · Build 26200 · Uptime 0d 0h 0m")
        self.os_label.setStyleSheet("color: #888; font-size: 12px;")
        title_info.addWidget(self.os_label)
        top_layout.addLayout(title_info)
        top_layout.addStretch()
        
        self.scan_btn = QPushButton("Scan system")
        self.scan_btn.setStyleSheet("background-color: #1a1a1f; border: 1px solid #333; padding: 8px 15px; border-radius: 5px;")
        top_layout.addWidget(self.scan_btn)
        
        self.tune_btn = QPushButton("⚡ Quick Tune-Up")
        self.tune_btn.setStyleSheet("background-color: #6A11CB; color: white; border: none; padding: 8px 15px; border-radius: 5px; font-weight: bold;")
        top_layout.addWidget(self.tune_btn)
        self.layout.addLayout(top_layout)
        
        # Health Score Card
        health_card = DashboardCard("")
        health_inner = QHBoxLayout()
        health_card.layout.addLayout(health_inner)
        
        self.health_circle = CircularProgressBar()
        health_inner.addWidget(self.health_circle)
        
        health_info = QVBoxLayout()
        health_info.setSpacing(5)
        health_title = QLabel("System Health Score")
        health_title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        health_info.addWidget(health_title)
        
        self.health_warning = QLabel("⚠ Everything looks good. System is optimized.")
        self.health_warning.setStyleSheet("color: #ffa500; font-size: 13px;")
        health_info.addWidget(self.health_warning)
        
        health_inner.addLayout(health_info)
        health_inner.addStretch()
        self.layout.addWidget(health_card)
        
        # Monitor Cards Row
        monitor_layout = QHBoxLayout()
        self.cpu_card = MonitorCard("CPU", "#00ff88")
        self.mem_card = MonitorCard("MEMORY", "#4158D0")
        self.gpu_card = MonitorCard("GPU", "#6A11CB")
        monitor_layout.addWidget(self.cpu_card)
        monitor_layout.addWidget(self.mem_card)
        monitor_layout.addWidget(self.gpu_card)
        self.layout.addLayout(monitor_layout)
        
        # Storage Card
        self.storage_card = DashboardCard("STORAGE")
        self.storage_grid = QVBoxLayout()
        self.storage_card.layout.addLayout(self.storage_grid)
        self.layout.addWidget(self.storage_card)
        
        # Bottom Row
        bottom_layout = QHBoxLayout()
        self.actions_card = DashboardCard("QUICK ACTIONS")
        self.alerts_card = DashboardCard("SYSTEM ALERTS")
        self.activity_card = DashboardCard("RECENT ACTIVITY")
        bottom_layout.addWidget(self.actions_card)
        bottom_layout.addWidget(self.alerts_card)
        bottom_layout.addWidget(self.activity_card)
        self.layout.addLayout(bottom_layout)
        
        self.layout.addStretch()

class NotificationBanner(QFrame):
    def __init__(self, message, button_text="View details", parent=None):
        super().__init__(parent)
        self.setObjectName("NotificationBanner")
        self.setFixedHeight(50)
        self.setStyleSheet("""
            QFrame#NotificationBanner {
                background-color: #1a1a1f;
                border: 1px solid #333;
                border-radius: 8px;
                margin: 10px 30px 0 30px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(15)
        
        # Icon (Matching the reference image: download icon)
        self.icon_label = QLabel("⬇️") # Use an emoji or a character that looks like it
        self.icon_label.setStyleSheet("color: #4158D0; font-size: 16px; background: transparent;")
        layout.addWidget(self.icon_label)
        
        self.msg_label = QLabel(message)
        self.msg_label.setStyleSheet("color: #d4d4d4; font-size: 13px; background: transparent;")
        layout.addWidget(self.msg_label)
        
        layout.addStretch()
        
        self.action_btn = QPushButton(button_text)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setFixedHeight(30)
        self.action_btn.setStyleSheet("""
            QPushButton {
                background-color: #4158D0;
                color: white;
                border: none;
                padding: 0 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4b6de3;
            }
        """)
        layout.addWidget(self.action_btn)
