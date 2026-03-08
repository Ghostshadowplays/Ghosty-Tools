import subprocess
import json
import os
import sys

# Get the path to the powershell script
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ps_script = os.path.join(project_root, "powershell", "ghostytools.ps1")

print(f"Testing PowerShell backend at: {ps_script}")

try:
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass",
         "-File", ps_script, "-Action", "SystemInfo", "-Json"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error: PowerShell returned exit code {result.returncode}")
        print(f"Stderr: {result.stderr}")
    else:
        print(f"Raw Output: {result.stdout}")
        data = json.loads(result.stdout)
        print("Successfully parsed JSON:")
        print(json.dumps(data, indent=4))
        
        if "OS" in data:
            print(f"Confirmed: OS is {data['OS']}")

except Exception as e:
    print(f"Test failed: {e}")
