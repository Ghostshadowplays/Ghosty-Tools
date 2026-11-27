import json
import os
from PyQt6.QtGui import QColor

class ThemeManager:
    DEFAULT_THEME = "Ghost Mint"
    DEFAULT_THEMES = {
        "Ghost Mint": {
            "primary": "#78e6c4",
            "secondary": "#93b8f5",
            "background": "#12151b",
            "surface": "#1b2028",
            "text": "#e9edf4",
            "accent": "#9befd3"
        },
        "Midnight Ind": {
            "primary": "#4158D0",
            "secondary": "#C850C0",
            "background": "#0f0f13",
            "surface": "#1a1a1f",
            "text": "#ffffff",
            "accent": "#4158D0"
        },
        "Deep Ocean": {
            "primary": "#0093E9",
            "secondary": "#80D0C7",
            "background": "#0b1116",
            "surface": "#151c24",
            "text": "#ffffff",
            "accent": "#0093E9"
        },
        "Dark Forest": {
            "primary": "#009345",
            "secondary": "#80D080",
            "background": "#0b160b",
            "surface": "#152415",
            "text": "#ffffff",
            "accent": "#009345"
        },
        "Neon Rose": {
            "primary": "#FF3CAC",
            "secondary": "#784BA0",
            "background": "#160b11",
            "surface": "#24151c",
            "text": "#ffffff",
            "accent": "#FF3CAC"
        },
        "Violet Night": {
            "primary": "#6A11CB",
            "secondary": "#2575FC",
            "background": "#110b16",
            "surface": "#1c1524",
            "text": "#ffffff",
            "accent": "#6A11CB"
        },
        "Warm Ember": {
            "primary": "#FBAB7E",
            "secondary": "#F7CE68",
            "background": "#16110b",
            "surface": "#241c15",
            "text": "#ffffff",
            "accent": "#FBAB7E"
        },
        "Clean Light": {
            "primary": "#4158D0",
            "secondary": "#8B5CF6",
            "background": "#f0f0f5",
            "surface": "#ffffff",
            "text": "#1a1a2e",
            "accent": "#4158D0"
        },
        "Light Warm": {
            "primary": "#d97706",
            "secondary": "#f59e0b",
            "background": "#faf8f5",
            "surface": "#ffffff",
            "text": "#1c1309",
            "accent": "#d97706"
        }
    }

    # Which themes count as "light" mode
    LIGHT_THEMES = {"Clean Light", "Light Warm"}

    def __init__(self, config_path="config/theme.json"):
        self.config_path = config_path
        self.current_theme = self.DEFAULT_THEME
        self.bg_intensity = 50
        self.custom_colors = {}
        self.load_settings()

    def load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.current_theme = data.get("current_theme", self.DEFAULT_THEME)
                    self.bg_intensity = data.get("bg_intensity", 50)
                    self.custom_colors = data.get("custom_colors", {})
            except:
                pass

    def save_settings(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump({
                "current_theme": self.current_theme,
                "bg_intensity": self.bg_intensity,
                "custom_colors": self.custom_colors
            }, f)

    def get_theme_colors(self):
        colors = self.DEFAULT_THEMES.get(self.current_theme, self.DEFAULT_THEMES[self.DEFAULT_THEME]).copy()
        if self.current_theme == "Custom":
            colors.update(self.custom_colors)
        return colors

    def set_theme(self, theme_name):
        if theme_name in self.DEFAULT_THEMES or theme_name == "Custom":
            self.current_theme = theme_name
            self.save_settings()

    def get_stylesheet(self):
        colors = self.get_theme_colors()
        factor = max(0.15, self.bg_intensity / 50.0)

        def adjust(value):
            return QColor(value).lighter(max(1, round(factor * 100))).name()

        def blend(first, second, weight):
            first, second = QColor(first), QColor(second)
            return QColor(*(round(a * (1 - weight) + b * weight)
                            for a, b in zip(first.getRgb()[:3], second.getRgb()[:3]))).name()

        background = adjust(colors["background"])
        surface = adjust(colors["surface"])
        muted = blend(colors["text"], background, 0.38)
        border = blend(surface, colors["text"], 0.15)
        hover = blend(surface, colors["text"], 0.08)
        sidebar = blend(background, surface, 0.25)
        primary_ink = "#11151b" if QColor(colors["primary"]).lightness() > 140 else "#ffffff"
        accent = colors["primary"]
        text = colors["text"]

        return f"""
            QMainWindow, QDialog {{
                background: {background}; color: {text};
            }}
            QWidget {{
                background: transparent; color: {text};
                font-family: 'Segoe UI'; font-size: 12px;
            }}
            QWidget#RightPanel {{ background: {background}; }}
            QFrame#AppearanceOverlay {{
                background: {surface}; border: 1px solid {border}; border-radius: 12px;
            }}
            QFrame#Sidebar {{
                background: {sidebar}; border: none; border-right: 1px solid {border};
            }}
            QFrame#HeaderFrame {{
                background: {background}; border: none; border-bottom: 1px solid {border};
            }}
            QLabel#BrandName {{ font-size: 21px; font-weight: 700; letter-spacing: 1px; }}
            QLabel#BrandTagline, QLabel#SectionTitle, QLabel#NavSection {{
                color: {muted}; font-size: 10px; font-weight: 600; letter-spacing: 1.5px;
            }}
            QLabel#NavSection {{ padding: 18px 12px 5px 12px; }}
            QLabel#MutedText {{ color: {muted}; font-size: 11px; }}
            QLabel#PageTitle {{ font-size: 26px; font-weight: 600; }}
            QLabel#Breadcrumb {{ color: {muted}; font-size: 11px; letter-spacing: 1px; }}
            QLabel#WorkspaceTitle {{ font-size: 14px; font-weight: 600; }}
            QLabel#HeroEyebrow {{ color: {accent}; font-size: 10px; font-weight: 600; letter-spacing: 2px; }}
            QLabel#HeroTitle {{ font-size: 32px; font-weight: 600; }}
            QLabel#MetricValue {{ font-size: 32px; font-weight: 600; }}
            QFrame#DashboardHero {{
                background: {surface}; border: 1px solid {border};
                border-top: 2px solid {accent}; border-radius: 12px;
            }}
            QFrame#DashboardCard, QFrame#MonitorCard {{
                background: {surface}; border: 1px solid {border}; border-radius: 10px;
            }}
            QPushButton {{
                background: {surface}; border: 1px solid {border}; border-radius: 7px;
                padding: 8px 14px; color: {text}; min-height: 16px;
            }}
            QPushButton:hover {{ background: {hover}; border-color: {accent}; }}
            QPushButton:pressed {{ background: {border}; }}
            QPushButton:disabled {{ color: {muted}; }}
            QPushButton:focus {{ border: 1px solid {accent}; }}
            QPushButton#PrimaryBtn {{
                background: {accent}; color: {primary_ink}; border-color: {accent}; font-weight: 600;
            }}
            QPushButton#PrimaryBtn:hover {{ background: {colors['accent']}; }}
            QPushButton#AppearanceMode:checked {{
                background: {hover}; border: 2px solid {accent}; color: {text};
            }}
            QPushButton#NavButton {{
                background: transparent; border: 1px solid transparent;
                border-radius: 7px; padding: 0; min-height: 37px; max-height: 37px;
            }}
            QPushButton#NavButton:hover {{ background: {hover}; }}
            QPushButton#NavButton:checked {{ background: {hover}; border-left: 3px solid {accent}; }}
            QPushButton#NavButton:focus {{ border: 1px solid {accent}; }}
            QLabel#NavTitle {{ color: {muted}; font-size: 12px; }}
            QLabel#NavChevron {{ color: {muted}; font-size: 16px; }}
            QPushButton#NavButton:checked QLabel#NavTitle {{ color: {text}; font-weight: 600; }}
            QPushButton#NavButton:checked QLabel#NavChevron {{ color: {accent}; }}
            QLineEdit#ToolSearch {{
                background: {surface}; border: 1px solid {border}; border-radius: 7px;
                padding: 9px 10px; font-size: 11px;
            }}
            QLineEdit#ToolSearch:focus {{ border-color: {accent}; }}
            QGroupBox {{
                background: {surface}; border: 1px solid {border}; border-radius: 9px;
                margin-top: 18px; padding: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 14px; padding: 0 5px;
                color: {muted}; font-size: 10px; font-weight: 600;
            }}
            QGroupBox#ActivityPane {{ margin: 0; border-radius: 0; border-width: 1px 0 0 0; }}
            QGroupBox#ActivityPane::title {{ color: transparent; }}
            QFrame#WorkspaceFooter {{ background: {surface}; border-top: 1px solid {border}; }}
            QTextEdit#ActivityOutput {{
                background: transparent; border: none; color: {text};
                font-family: 'Consolas', 'Menlo', monospace; font-size: 11px;
            }}
            QPushButton#LogToggle {{ background: transparent; border: none; text-align: left; padding: 4px 8px; }}
            QPushButton#QuickAction {{ text-align: left; background: transparent; border-color: {border}; }}
            QSplitter::handle {{ background: {border}; }}
            QSplitter::handle:hover {{ background: {accent}; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ border: none; background: transparent; }}
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
                background: {background}; border: 1px solid {border}; border-radius: 6px;
                padding: 7px; color: {text}; selection-background-color: {accent};
            }}
            QComboBox QAbstractItemView {{ background: {surface}; color: {text}; selection-background-color: {hover}; }}
            QTreeWidget, QListWidget {{
                background: {surface}; border: 1px solid {border}; border-radius: 8px; color: {text};
            }}
            QTreeWidget::item, QListWidget::item {{ padding: 8px; border-bottom: 1px solid {border}; }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background: {hover}; color: {text};
            }}
            QHeaderView::section {{
                background: {surface}; color: {muted}; padding: 8px;
                border: none; border-bottom: 1px solid {border}; font-weight: 600;
            }}
            QTabWidget::pane {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; }}
            QTabBar::tab {{ background: transparent; color: {muted}; padding: 11px 16px; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {accent}; }}
            QProgressBar {{ background: {hover}; border: none; border-radius: 3px; text-align: center; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
            QSlider::groove:horizontal {{
                background: {border}; height: 4px; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {accent}; width: 16px; margin: -6px 0; border-radius: 8px;
            }}
            QScrollBar:vertical {{ background: transparent; width: 7px; margin: 0; }}
            QScrollBar:horizontal {{ background: transparent; height: 7px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 24px; border-radius: 3px; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 24px; border-radius: 3px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
            QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
            QFrame#NotificationBanner {{ background: {hover}; border-bottom: 1px solid {border}; }}
            QToolTip {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 6px; }}
        """
