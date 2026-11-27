"""Small vector marks drawn consistently on every supported desktop."""

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer


_PATHS = {
    "Dashboard": '<path d="M3 11 12 3l9 8v9a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    "System": '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4M7 11h3l2-4 2 7 2-3h2"/>',
    "Security": '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6zM8 12l3 3 5-6"/>',
    "Network": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18"/>',
    "Monitor": '<path d="M3 19V5m0 14h18M6 14l4-5 4 3 6-7"/>',
    "Privacy": '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
    "Debloat": '<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
    "Apps": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 17h7m-3.5-3.5v7"/>',
    "Cleanup": '<path d="m13 3 3 3-8 9-4-4zM4 11l-2 7 4 4 7-2-5-5m1 4-4-4M18 10v6m-3-3h6"/>',
    "Storage": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 14h18m-5 3h2"/><circle cx="8" cy="9" r="2"/>',
    "Hardware": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/><rect x="10" y="10" width="4" height="4"/>',
    "Events": '<path d="M7 3h10v3h3v15H4V6h3zM7 3v5h10V3M8 12h8m-8 4h6"/>',
    "Services": '<path d="m14 4 1 4 4 1 2-2a7 7 0 0 1-9 9l-6 6-4-4 6-6a7 7 0 0 1 9-9z"/>',
    "Automation": '<path d="m14 2-9 12h6l-1 8 9-12h-6z"/>',
    "Passwords": '<circle cx="8" cy="8" r="5"/><path d="m12 12 9 9m-4-4 3-3m-6 0 3-3"/>',
    "Customization": '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',
    "Settings": '<path d="m9 3-1 3-3 1-2 5 2 5 3 1 1 3h6l1-3 3-1 2-5-2-5-3-1-1-3z"/><circle cx="12" cy="12" r="3"/>',
    "Gaming": '<path d="M7 7h10c3 0 6 12 3 13-2 1-4-4-6-4h-4c-2 0-4 5-6 4C1 19 4 7 7 7zM6 11h6m-3-3v6m7-3h.1m3 2h.1"/>',
    "Info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
    "search": '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    "ghost": '<path d="M5 20V10a7 7 0 0 1 14 0v10l-3-2-4 3-4-3z"/><path d="M9 10v2m6-2v2"/>',
}


def tool_icon(name, color="#8c9d99", size=24):
    """Render a vector icon without relying on platform-specific icon fonts."""
    drawing = _PATHS.get(name, _PATHS["System"])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round">{drawing}</svg>'
    )
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
