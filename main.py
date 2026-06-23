import sys
import os
import logging
import traceback
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import GhostyTool
from src.utils.helpers import get_logs_dir, get_os_info

# Determine version
VERSION = "v7.3"

def setup_logging():
    """Configure logging to both file and console."""
    logs_dir = get_logs_dir()
    log_file = os.path.join(logs_dir, f"ghostytools_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file

def global_exception_handler(exctype, value, tb):
    """Global exception handler to capture unhandled exceptions."""
    logger = logging.getLogger("CRASH_REPORT")
    os_info = get_os_info()
    
    error_msg = f"Unhandled Exception: {exctype.__name__}: {value}\n"
    error_msg += f"App Version: {VERSION}\n"
    error_msg += f"OS Info: {os_info}\n"
    error_msg += "Traceback:\n"
    error_msg += "".join(traceback.format_exception(exctype, value, tb))
    
    logger.critical(error_msg)
    
    # Optionally show a message box (but only if QApplication is running)
    if QApplication.instance():
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Ghosty Tools - Fatal Error", 
                           f"An unhandled error occurred:\n{value}\n\nLogs saved to: {get_logs_dir()}")
    
    # Still call the default handler
    sys.__excepthook__(exctype, value, tb)

def main():
    """Main entry point for Ghosty Tools."""
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Ghosty Tools {VERSION} on {sys.platform}")
    
    # Install global exception handler
    sys.excepthook = global_exception_handler
    
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
