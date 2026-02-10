import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import GhostyTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for Ghosty Tools."""
    try:
        app = QApplication(sys.argv)
        
        # Initialize the main window
        window = GhostyTool()
        window.show()
        
        # Execute the application
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Application failed to start: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
