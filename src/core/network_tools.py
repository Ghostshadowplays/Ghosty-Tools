import socket
import requests
import time
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

class NetworkTools:
    GAMING_PRESETS = {
        "CS2": ["162.254.192.1", "155.133.248.1"], # Valve servers
        "FACEIT": ["31.186.224.112"],
        "PUBG": ["52.94.196.1"],
        "Twitch": ["twitch.tv"],
        "YouTube": ["youtube.com"]
    }

    @staticmethod
    def ping_multi(targets=None):
        """Ping multiple targets and return latency, jitter, and loss."""
        if targets is None:
            targets = ["8.8.8.8", "1.1.1.1", "google.com"]
        
        results = {}
        for target in targets:
            results[target] = NetworkTools.ping_stats(target)
        return results

    @staticmethod
    def ping_stats(target, count=4):
        """Calculate latency, jitter, and packet loss for a target."""
        from src.utils.helpers import run_command
        import re
        
        latencies = []
        loss = 0
        
        if sys.platform == "win32":
            cmd = ["ping", "-n", str(count), target]
        else:
            cmd = ["ping", "-c", str(count), target]
            
        proc = run_command(cmd)
        
        if sys.platform == "win32":
            # Extract latencies and loss from Windows ping output
            # Example: Reply from 8.8.8.8: bytes=32 time=10ms TTL=117
            times = re.findall(r"time[=<](\d+)ms", proc.stdout)
            latencies = [float(t) for t in times]
            
            loss_match = re.search(r"\((\d+)% loss\)", proc.stdout)
            if loss_match:
                loss = int(loss_match.group(1))
        else:
            # Extract latencies and loss from Linux/macOS ping output
            # Example: 64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=10.2 ms
            times = re.findall(r"time=(\d+\.?\d*) ms", proc.stdout)
            latencies = [float(t) for t in times]
            
            loss_match = re.search(r"(\d+)% packet loss", proc.stdout)
            if loss_match:
                loss = int(loss_match.group(1))

        if not latencies:
            return {"avg": -1, "jitter": -1, "loss": 100}
            
        avg = sum(latencies) / len(latencies)
        jitter = 0
        if len(latencies) > 1:
            jitter = sum(abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))) / (len(latencies) - 1)
            
        return {"avg": avg, "jitter": jitter, "loss": loss}

    @staticmethod
    def get_auto_verdict():
        """Determine where the network issue lies: local, ISP, or remote."""
        # 1. Ping Gateway (local)
        # 2. Ping ISP/Next Hop (ISP)
        # 3. Ping global target (Remote)
        # This is a simplified version.
        
        local = NetworkTools.ping_stats("192.168.1.1", count=2) # Common gateway
        remote = NetworkTools.ping_stats("8.8.8.8", count=2)
        
        if local["loss"] > 50:
            return "LOCAL ISSUE (Gateway unreachable)"
        if remote["loss"] > 50:
            return "ISP / GLOBAL ISSUE (Gateway OK, Remote unreachable)"
        if remote["avg"] > 150:
            return "HIGH LATENCY (ISP / Remote)"
            
        return "HEALTHY"

    @staticmethod
    def run_traceroute(target):
        """Run traceroute to a target."""
        from src.utils.helpers import run_command
        if sys.platform == "win32":
            cmd = ["tracert", "-d", target]
        else:
            cmd = ["traceroute", "-n", target]
        
        return run_command(cmd).stdout

    @staticmethod
    def speedtest_ookla():
        """Run Ookla speedtest-cli if available, return JSON output."""
        from src.utils.helpers import run_command
        import json
        try:
            # Assumes 'speedtest' is the official Ookla CLI (v1.x) which supports --format=json
            proc = run_command(["speedtest", "--format=json", "--accept-license", "--accept-gdpr"])
            if proc.returncode == 0:
                return json.loads(proc.stdout)
        except Exception:
            pass
        return None

    @staticmethod
    def get_ip_intelligence():
        """Get local and public IP details."""
        details = {
            "local_ip": "N/A",
            "public_ip": "N/A",
            "isp": "N/A",
            "location": "N/A"
        }
        try:
            # Local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            details["local_ip"] = s.getsockname()[0]
            s.close()
        except Exception as e:
            logger.error(f"Error getting local IP: {e}")

        try:
            # Public IP and ISP info
            response = requests.get("https://ipapi.co/json/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                details["public_ip"] = data.get("ip", "N/A")
                details["isp"] = data.get("org", "N/A")
                details["location"] = f"{data.get('city', 'N/A')}, {data.get('region', 'N/A')}, {data.get('country_name', 'N/A')}"
        except Exception as e:
            logger.error(f"Error getting public IP info: {e}")
            
        return details

    @staticmethod
    def benchmark_dns():
        """Compare response times of popular DNS servers."""
        dns_servers = {
            "Google (8.8.8.8)": "8.8.8.8",
            "Cloudflare (1.1.1.1)": "1.1.1.1",
            "OpenDNS (208.67.222.222)": "208.67.222.222",
            "Quad9 (9.9.9.9)": "9.9.9.9"
        }
        results = []
        host = "www.google.com"

        for name, ip in dns_servers.items():
            try:
                # Use platform-specific ping or socket-based check? 
                # Better to use socket to measure actual DNS resolution time if possible,
                # but simple ping is a good proxy for latency.
                # Actually, measuring resolution time is better.
                start = time.time()
                # We can't easily force a specific DNS server with socket.gethostbyname
                # without using a 3rd party lib like dnspython. 
                # Let's use subprocess to call 'nslookup' or 'dig'?
                
                from src.utils.helpers import run_command
                cmd = []
                if sys.platform == "win32":
                    cmd = ["nslookup", host, ip]
                else:
                    cmd = ["nslookup", host, ip] # nslookup is common on Linux/macOS too

                proc = run_command(cmd, timeout=2)
                end = time.time()
                
                if proc.returncode == 0:
                    latency = (end - start) * 1000
                    results.append({"name": name, "latency": latency})
                else:
                    results.append({"name": name, "latency": -1}) # Failed
            except Exception:
                results.append({"name": name, "latency": -1})

        return sorted(results, key=lambda x: x["latency"] if x["latency"] > 0 else float('inf'))

    @staticmethod
    def port_scan(target="127.0.0.1", ports=None):
        """Simple port scanner for the local machine."""
        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5900, 8080]
        
        open_ports = []
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    if s.connect_ex((target, port)) == 0:
                        open_ports.append(port)
            except Exception:
                pass
        return open_ports
