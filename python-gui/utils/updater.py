import os
import sys
import time
import subprocess
import shutil

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

def main():
    if len(sys.argv) < 3:
        print("Usage: updater.py <old_exe_or_script> <new_file>")
        return

    old_file = sys.argv[1]
    new_file = sys.argv[2]
    
    print(f"Updating {old_file} with {new_file}...")
    
    # Wait a bit for the main process to exit
    time.sleep(2)
    
    try:
        # If it's an EXE, we might need to handle it differently, 
        # but generally replacing the file should work if it's closed.
        if os.path.exists(old_file):
            os.remove(old_file)
        
        shutil.move(new_file, old_file)
        print("Update applied successfully.")
        
        # Restart the tool
        if old_file.endswith(".py"):
            subprocess.Popen([sys.executable, old_file], creationflags=CREATE_NO_WINDOW)
        else:
            subprocess.Popen([old_file], creationflags=CREATE_NO_WINDOW)
            
    except Exception as e:
        print(f"Error during update: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()
