import sys
import os
import time
import subprocess
import shutil
import logging
from datetime import datetime

def setup_updater_logging():
    # Try to find the logs directory
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        logs_dir = os.path.join(base, 'GhostyTools', 'logs')
    else:
        logs_dir = os.path.join(os.path.expanduser('~'), '.config', 'GhostyTools', 'logs')
    
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "updater.log")
    
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("Updater")

def is_file_locked(file_path):
    """Checks if a file is locked by another process."""
    if not os.path.exists(file_path):
        return False
    try:
        # On Windows, renaming a file to itself will fail if it's open/running
        os.rename(file_path, file_path)
        return False
    except OSError:
        return True

def main():
    """
    GhostyUpdater - A minimal updater for GhostyTools.
    Arguments:
        arg1: path to the new EXE file
        arg2: path to the old EXE file
    """
    logger = setup_updater_logging()
    logger.info("Starting updater...")

    if len(sys.argv) < 3:
        logger.error("Insufficient arguments.")
        sys.exit(1)

    new_exe = os.path.abspath(sys.argv[1])
    old_exe = os.path.abspath(sys.argv[2])
    backup_exe = old_exe + ".bak"

    logger.info(f"Target EXE: {old_exe}")
    logger.info(f"New EXE: {new_exe}")

    # 1. Wait until the old EXE is no longer running
    max_wait = 60
    waited = 0
    while is_file_locked(old_exe) and waited < max_wait:
        time.sleep(1)
        waited += 1
        if waited % 5 == 0:
            logger.info(f"Waiting for {old_exe} to close... ({waited}s)")

    if is_file_locked(old_exe):
        logger.error(f"Timed out waiting for {old_exe} to close.")
        sys.exit(1)

    # 2. Perform update with rollback support
    try:
        # Create backup if it doesn't exist (should have been created by UpdateManager, but just in case)
        if os.path.exists(old_exe) and not os.path.exists(backup_exe):
            shutil.copy2(old_exe, backup_exe)
            logger.info(f"Created backup at {backup_exe}")

        # Replace old with new
        if os.path.exists(old_exe):
            os.remove(old_exe)
        
        if os.path.exists(new_exe):
            os.makedirs(os.path.dirname(old_exe), exist_ok=True)
            shutil.move(new_exe, old_exe)
            logger.info("Successfully replaced EXE.")
            
            # 3. Relaunch
            logger.info(f"Relaunching {old_exe}...")
            subprocess.Popen([old_exe], shell=False)
            
            # Remove backup on success after some delay or next run?
            # For now keep it for safety.
    except Exception as e:
        logger.error(f"Update failed: {e}")
        # Rollback
        if os.path.exists(backup_exe):
            logger.info("Attempting rollback...")
            try:
                if os.path.exists(old_exe):
                    os.remove(old_exe)
                shutil.copy2(backup_exe, old_exe)
                logger.info("Rollback successful. Relaunching original...")
                subprocess.Popen([old_exe], shell=False)
            except Exception as re:
                logger.error(f"Rollback failed: {re}")
        sys.exit(1)

    logger.info("Updater finished successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
