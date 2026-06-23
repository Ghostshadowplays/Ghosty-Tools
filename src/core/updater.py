import sys
import os
import time
import subprocess

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
    if len(sys.argv) < 3:
        sys.exit(1)

    new_exe = os.path.abspath(sys.argv[1])
    old_exe = os.path.abspath(sys.argv[2])

    # 1. Wait until the old EXE is no longer running
    # We wait up to 30 seconds
    max_wait = 60
    waited = 0
    while is_file_locked(old_exe) and waited < max_wait:
        time.sleep(0.5)
        waited += 1

    # 2. Once the old EXE is unlocked, replace it
    try:
        if os.path.exists(old_exe):
            os.remove(old_exe)
        
        if os.path.exists(new_exe):
            # Ensure the directory for old_exe exists (it should, but just in case)
            os.makedirs(os.path.dirname(old_exe), exist_ok=True)
            os.rename(new_exe, old_exe)
            
            # 3. Relaunch the updated GhostyTools.exe
            # Use start_new_session=True on Unix (though this is Windows-specific)
            # On Windows, we just use Popen
            subprocess.Popen([old_exe], shell=False)
    except Exception as e:
        # Fallback: if something fails, we just exit. 
        # In a production app, we might want to log this.
        pass

    # 4. Exit the updater
    sys.exit(0)

if __name__ == "__main__":
    main()
