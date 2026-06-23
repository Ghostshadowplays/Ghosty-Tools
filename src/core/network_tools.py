import socket
import requests
import time
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

class NetworkTools:
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
