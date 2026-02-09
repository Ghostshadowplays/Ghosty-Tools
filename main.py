import sys
from PyQt6.QtWidgets import QApplication
from src.utils.helpers import is_admin, elevate_privileges
from src.gui.main_window import GhostyTool

def main():
    # Ensure admin privileges
    if not is_admin():
        elevate_privileges()
        return

    # Start Application
    app = QApplication(sys.argv)
    window = GhostyTool()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
