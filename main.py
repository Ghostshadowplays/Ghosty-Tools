import sys
import os

# Fix for speedtest-cli and other libraries that expect sys.stdout/stderr to exist
# and have a fileno (common in PyInstaller --noconsole mode)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

from PyQt6.QtWidgets import QApplication
from src.utils.helpers import is_admin, elevate_privileges
from src.gui.main_window import GhostyTool

def main():
    # Start Application
    app = QApplication(sys.argv)
    window = GhostyTool()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
