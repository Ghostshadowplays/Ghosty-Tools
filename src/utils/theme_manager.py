import json
import os
from PyQt6.QtGui import QColor

class ThemeManager:
    DEFAULT_THEMES = {
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
        }
    }

    def __init__(self, config_path="config/theme.json"):
        self.config_path = config_path
        self.current_theme = "Midnight Ind"
        self.bg_intensity = 50
        self.custom_colors = {}
        self.load_settings()

    def load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.current_theme = data.get("current_theme", "Midnight Ind")
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
        if self.current_theme == "Custom":
            return self.custom_colors
        return self.DEFAULT_THEMES.get(self.current_theme, self.DEFAULT_THEMES["Midnight Ind"])

    def set_theme(self, theme_name):
        if theme_name in self.DEFAULT_THEMES or theme_name == "Custom":
            self.current_theme = theme_name
            self.save_settings()

    def get_stylesheet(self):
        colors = self.get_theme_colors().copy()
        
        # Adjust background and surface based on intensity
        # Map 0-100 to a reasonable brightness range for dark themes
        # 0 = very dark, 100 = lighter (but still dark)
        bg = QColor(colors['background'])
        surf = QColor(colors['surface'])
        
        # Simple brightness adjustment
        factor = self.bg_intensity / 50.0
        
        def adjust(color, f):
            c = QColor(color)
            h, s, v, a = c.getHsv()
            new_v = max(0, min(255, int(v * f)))
            c.setHsv(h, s, new_v, a)
            return c.name()

        colors['background'] = adjust(colors['background'], factor)
        colors['surface'] = adjust(colors['surface'], factor)

        return f"""
            QMainWindow, QDialog {{
                background-color: {colors['background']};
                color: {colors['text']};
            }}
            QWidget {{
                background-color: transparent;
                color: {colors['text']};
                font-family: 'Segoe UI';
            }}
            QWidget#RightPanel {{
                background-color: {colors['background']};
            }}
            QFrame#Sidebar {{
                background-color: {colors['background']};
                border-right: 1px solid #222;
            }}
            QFrame#HeaderFrame {{
                background-color: {colors['surface']};
                border-bottom: 1px solid #333;
            }}
            QPushButton {{
                background-color: {colors['surface']};
                border: 1px solid #333;
                border-radius: 5px;
                padding: 5px 15px;
                color: {colors['text']};
            }}
            QPushButton:hover {{
                background-color: #333;
                border-color: {colors['primary']};
            }}
            QPushButton#PrimaryBtn {{
                background-color: {colors['primary']};
                border: none;
                font-weight: bold;
                color: white;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {colors['accent']};
            }}
            QLabel {{
                color: {colors['text']};
            }}
            QGroupBox {{
                border: 1px solid #333;
                border-radius: 8px;
                margin-top: 15px;
                background-color: {colors['surface']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                color: {colors['primary']};
                font-weight: bold;
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
                background-color: #111;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px;
                color: {colors['text']};
                selection-background-color: {colors['primary']};
            }}
            QTreeWidget, QListWidget {{
                background-color: {colors['surface']};
                border: 1px solid #333;
                border-radius: 8px;
                color: {colors['text']};
            }}
            QTreeWidget::item, QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid #222;
            }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background-color: {colors['primary']};
                color: white;
            }}
            QHeaderView::section {{
                background-color: #1a1a1f;
                color: #888;
                padding: 5px;
                border: none;
                font-weight: bold;
            }}
            QTabWidget::pane {{
                border: 1px solid #333;
                border-radius: 10px;
                background-color: {colors['surface']};
                top: -1px;
            }}
            QTabBar::tab {{
                background: {colors['background']};
                color: #888;
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 5px;
            }}
            QTabBar::tab:selected {{
                background: {colors['surface']};
                color: white;
                border-bottom: 2px solid {colors['primary']};
            }}
            QProgressBar {{
                background-color: #2a2a2a;
                border: none;
                border-radius: 2px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {colors['primary']};
                border-radius: 2px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {colors['background']};
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #333;
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QFrame#DashboardCard {{
                background-color: {colors['surface']};
                border: 1px solid #333;
                border-radius: 10px;
            }}
            QFrame#DashboardCard:hover {{
                border-color: {colors['primary']};
            }}
        """
