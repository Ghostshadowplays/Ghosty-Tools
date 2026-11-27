"""Shared widgets for the Ghosty control room."""

from collections import deque

from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath, QPixmap, QPaintEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGridLayout, QProgressBar, QSizePolicy, QStackedWidget, QLayout, QTextBrowser,
)

from src.gui.icons import tool_icon
from src.utils.helpers import get_resource_path


class WorkspaceStack(QStackedWidget):
    """Size the scrollable workspace to the active page, not the largest tool."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.currentChanged.connect(self.updateGeometry)

    def sizeHint(self):
        page = self.currentWidget()
        return page.sizeHint() if page else super().sizeHint()

    def minimumSizeHint(self):
        page = self.currentWidget()
        return QSize(0, page.minimumSizeHint().height()) if page else super().minimumSizeHint()


class NavButton(QPushButton):
    def __init__(self, title, subtitle="", icon_text="", count=None, parent=None):
        super().__init__(parent)
        self._title = title
        self.search_text = f"{title} {subtitle}".casefold()
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setFixedHeight(39)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(subtitle or title)
        self.setAccessibleName(title)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.icon_label)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("NavTitle")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.title_label)
        layout.addStretch()
        self.chevron_label = QLabel("›")
        self.chevron_label.setObjectName("NavChevron")
        self.chevron_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.chevron_label)
        self._accent = "#78e6c4"
        self.toggled.connect(self.update_style)
        self.update_style()

    def text(self):
        return self._title

    def set_accent(self, color):
        self._accent = color
        self.update_style()

    def update_style(self):
        color = self._accent if self.isChecked() else "#849691"
        self.icon_label.setPixmap(tool_icon(self._title, color, 18).pixmap(18, 18))


class CircularProgressBar(QWidget):
    """The existing health-score interface, presented as a segmented readout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._has_reading = False
        self._status = "Waiting for a reading"
        self._color = QColor("#78e6c4")
        self.setFixedSize(210, 108)
        self.setAccessibleName("System health score")

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = max(0, min(100, int(val)))
        self._has_reading = True
        self.setAccessibleDescription(f"{self._value} out of 100. {self._status}")
        self.update()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, val):
        self._status = val
        self.setAccessibleDescription(f"{self._value} out of 100. {self._status}")
        self.update()

    def paintEvent(self, event: QPaintEvent | None = None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self.palette().windowText().color())
        painter.setFont(QFont("Segoe UI", 38, QFont.Weight.DemiBold))
        painter.drawText(QRectF(0, 0, 110, 63), Qt.AlignmentFlag.AlignLeft, str(self._value) if self._has_reading else "—")
        painter.setPen(QColor("#81958e"))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(QRectF(114, 29, 90, 28), Qt.AlignmentFlag.AlignLeft, "/ 100")
        painter.setPen(self._color)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        painter.drawText(QRectF(0, 65, 210, 20), Qt.AlignmentFlag.AlignLeft, self._status)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(20):
            active = self._value > index * 5
            painter.setBrush(self._color if active else QColor("#293b35"))
            painter.drawRoundedRect(QRectF(index * 10.5, 96, 7, 5), 1.5, 1.5)


class Sparkline(QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.samples = deque(maxlen=32)
        self.color = QColor(color)
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def add_sample(self, value):
        self.samples.append(max(0, min(100, value)))
        self.update()

    def paintEvent(self, event: QPaintEvent | None = None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.rect().adjusted(1, 4, -1, -3)
        grid = QColor(self.color)
        grid.setAlpha(25)
        painter.setPen(QPen(grid, 1))
        painter.drawLine(bounds.bottomLeft(), bounds.bottomRight())
        painter.drawLine(bounds.left(), bounds.center().y(), bounds.right(), bounds.center().y())
        if len(self.samples) < 2:
            return
        points = [
            QPointF(
                bounds.left() + index * bounds.width() / (len(self.samples) - 1),
                bounds.bottom() - sample * bounds.height() / 100,
            )
            for index, sample in enumerate(self.samples)
        ]
        line = QPainterPath(points[0])
        for point in points[1:]:
            line.lineTo(point)
        fill = QPainterPath(line)
        fill.lineTo(QPointF(bounds.bottomRight()))
        fill.lineTo(QPointF(bounds.bottomLeft()))
        fill.closeSubpath()
        shade = QColor(self.color)
        shade.setAlpha(20)
        painter.fillPath(fill, shade)
        painter.setPen(QPen(self.color, 1.7))
        painter.drawPath(line)


class PageHeader(QWidget):
    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 12)
        self.layout.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("PageTitle")
        self.layout.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("MutedText")
            self.subtitle_label.setWordWrap(True)
            self.layout.addWidget(self.subtitle_label)


class DashboardCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(12)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        if title:
            self.title_label = QLabel(title.upper())
            self.title_label.setObjectName("SectionTitle")
            self.layout.addWidget(self.title_label)


class MonitorCard(DashboardCard):
    def __init__(self, title, color="#78e6c4", parent=None):
        super().__init__(title, parent)
        self.setObjectName("MonitorCard")
        self.layout.setContentsMargins(18, 14, 18, 14)
        self.layout.setSpacing(8)
        self.value_label = QLabel("—")
        self.value_label.setObjectName("MetricValue")
        self.layout.addWidget(self.value_label)
        self.details_label = QLabel("Waiting for a reading")
        self.details_label.setObjectName("MutedText")
        self.details_label.setWordWrap(True)
        self.layout.addWidget(self.details_label)
        self.sparkline = Sparkline(color)
        self.layout.addWidget(self.sparkline)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(3)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(
            f"QProgressBar {{ background: transparent; border: none; }}"
            f"QProgressBar::chunk {{ background: {color}; }}"
        )
        self.layout.addWidget(self.bar)

    def set_reading(self, value, details=None):
        value = max(0, min(100, int(value)))
        self.value_label.setText(f"{value}%")
        self.bar.setValue(value)
        self.sparkline.add_sample(value)
        if details is not None:
            self.details_label.setText(details)


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.layout.setContentsMargins(28, 26, 28, 26)
        self.layout.setSpacing(20)

        hero = QFrame()
        hero.setObjectName("DashboardHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 22, 26, 22)
        hero_layout.setSpacing(22)
        intro = QVBoxLayout()
        intro.setSpacing(8)
        eyebrow = QLabel("GHOSTY TOOLS  /  CONTROL ROOM")
        eyebrow.setObjectName("HeroEyebrow")
        intro.addWidget(eyebrow)
        self.title_label = QLabel("Your machine.\nYour command.")
        self.title_label.setObjectName("HeroTitle")
        intro.addWidget(self.title_label)
        self.os_label = QLabel("Reading your system…")
        self.os_label.setObjectName("MutedText")
        self.os_label.setWordWrap(True)
        intro.addWidget(self.os_label)
        hero_layout.addLayout(intro, 1)
        self.mascot_label = QLabel()
        self.mascot_label.setAccessibleName("Ghosty mascot")
        self.mascot_label.setFixedSize(190, 145)
        self.mascot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mascot = QPixmap(get_resource_path("images/ghostmascot.png"))
        if not mascot.isNull():
            self.mascot_label.setPixmap(mascot.scaled(
                190, 145, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        self.mascot_label.hide()
        hero_layout.addWidget(self.mascot_label)
        health = QVBoxLayout()
        health.setSpacing(6)
        health_title = QLabel("SYSTEM PULSE")
        health_title.setObjectName("SectionTitle")
        health.addWidget(health_title)
        self.health_circle = CircularProgressBar()
        health.addWidget(self.health_circle)
        self.health_warning = QLabel("Checking CPU, memory and storage…")
        self.health_warning.setObjectName("MutedText")
        self.health_warning.setWordWrap(True)
        self.health_warning.setMaximumWidth(250)
        health.addWidget(self.health_warning)
        hero_layout.addLayout(health)
        self.layout.addWidget(hero)

        self.system_card = DashboardCard("Your system / hardware & operating system")
        overview_actions = QHBoxLayout()
        self.system_summary = QLabel("Hardware details are collected in the background.")
        self.system_summary.setObjectName("MutedText")
        self.system_summary.setWordWrap(True)
        overview_actions.addWidget(self.system_summary, 1)
        self.system_details_toggle = QPushButton("System details")
        self.system_details_toggle.setCheckable(True)
        self.system_refresh_btn = QPushButton("Refresh")
        self.system_copy_btn = QPushButton("Copy")
        self.system_copy_btn.setEnabled(False)
        overview_actions.addWidget(self.system_details_toggle)
        overview_actions.addWidget(self.system_refresh_btn)
        overview_actions.addWidget(self.system_copy_btn)
        self.system_card.layout.addLayout(overview_actions)
        self.system_details = QTextBrowser()
        self.system_details.setAccessibleName("Full system overview")
        self.system_details.setMinimumHeight(260)
        self.system_details.setOpenExternalLinks(False)
        self.system_details.hide()
        self.system_details_toggle.toggled.connect(self.system_details.setVisible)
        self.system_details_toggle.toggled.connect(
            lambda expanded: self.system_details_toggle.setText("Hide details" if expanded else "System details")
        )
        self.system_card.layout.addWidget(self.system_details)
        self.layout.addWidget(self.system_card)

        telemetry_heading = QHBoxLayout()
        label = QLabel("LIVE TELEMETRY")
        label.setObjectName("SectionTitle")
        telemetry_heading.addWidget(label)
        telemetry_heading.addStretch()
        note = QLabel("Recent samples · refreshes every 2 seconds")
        note.setObjectName("MutedText")
        telemetry_heading.addWidget(note)
        self.layout.addLayout(telemetry_heading)
        monitors = QHBoxLayout()
        monitors.setSpacing(12)
        self.cpu_card = MonitorCard("Processor", "#78e6c4")
        self.mem_card = MonitorCard("Memory", "#93b8f5")
        self.gpu_card = MonitorCard("Graphics", "#c5adf3")
        self.gpu_card.details_label.setText("Waiting for a GPU sensor")
        for card in (self.cpu_card, self.mem_card, self.gpu_card):
            monitors.addWidget(card, 1)
        self.layout.addLayout(monitors)

        lower = QGridLayout()
        lower.setSpacing(14)
        lower.setColumnStretch(0, 3)
        lower.setColumnStretch(1, 2)
        self.actions_card = DashboardCard("Make your next move")
        self.scan_btn = QPushButton("Run security scan")
        self.scan_btn.setObjectName("PrimaryBtn")
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tune_btn = QPushButton("Quick tune-up")
        self.tune_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        primary_actions = QHBoxLayout()
        primary_actions.setSpacing(8)
        primary_actions.addWidget(self.scan_btn, 1)
        primary_actions.addWidget(self.tune_btn, 1)
        self.actions_card.layout.addLayout(primary_actions)
        self.storage_card = DashboardCard("Storage / space to breathe")
        self.storage_grid = QVBoxLayout()
        self.storage_grid.setSpacing(6)
        self.storage_card.layout.addLayout(self.storage_grid)
        self.alerts_card = DashboardCard("System signals")
        self.activity_card = DashboardCard("Recent activity")
        lower.addWidget(self.actions_card, 0, 0)
        lower.addWidget(self.alerts_card, 0, 1)
        lower.addWidget(self.storage_card, 1, 0)
        lower.addWidget(self.activity_card, 1, 1)
        self.layout.addLayout(lower)
        self.layout.addStretch()

    def resizeEvent(self, event: QResizeEvent | None = None) -> None:
        super().resizeEvent(event)
        pixmap = self.mascot_label.pixmap()
        self.mascot_label.setVisible(self.width() >= 860 and pixmap is not None and not pixmap.isNull())


class NotificationBanner(QFrame):
    def __init__(self, message, button_text="View details", parent=None):
        super().__init__(parent)
        self.setObjectName("NotificationBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 10, 24, 10)
        layout.setSpacing(14)
        self.icon_label = QLabel("↗")
        self.icon_label.setObjectName("HeroEyebrow")
        layout.addWidget(self.icon_label)
        self.msg_label = QLabel(message)
        self.msg_label.setWordWrap(True)
        layout.addWidget(self.msg_label, 1)
        self.action_btn = QPushButton(button_text)
        self.action_btn.setObjectName("PrimaryBtn")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.action_btn)
