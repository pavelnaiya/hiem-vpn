import time
import requests
from backend.logger import log
from backend.fsm import fsm, ProxyState
from backend.config_generator import config
from backend.tor_controller import tor
from backend.network_manager import net

class ProxyManager:
    def __init__(self):
        self.is_connected = False
        self.last_ip_info = {}

    def fetch_ip_info(self):
        log.info("Fetching IP info via Tor...")
        proxies = {'http': "http://127.0.0.1:8118", 'https': "http://127.0.0.1:8118"}
        try:
            res = requests.get("http://ip-api.com/json/", proxies=proxies, timeout=10)
            if res.status_code == 200:
                self.last_ip_info = res.json()
                return self.last_ip_info
        except Exception as e:
            log.error(f"IP fetch failed: {e}")
        return None

    def start_engines(self):
        from backend.event_bus import event_bus
        if self.is_connected:
            return
            
        event_bus.push({"type": "status", "status": "Connecting", "message": "Rendering configurations..."})
        config.render_immutable_configs()
        
        event_bus.push({"type": "status", "status": "Connecting", "message": "Starting Tor network service..."})
        tor.spawn()
        
        event_bus.push({"type": "status", "status": "Connecting", "message": "Bootstrapping Tor circuits..."})
        tor.wait_for_bootstrap()
        
        event_bus.push({"type": "status", "status": "Connecting", "message": "Configuring system proxy settings..."})
        net.enable_proxy(8118)
        self.is_connected = True
        
        event_bus.push({"type": "status", "status": "Connecting", "message": "Fetching secure IP info..."})
        self.fetch_ip_info()

    def stop_engines(self):
        net.disable_proxy()
        tor.killpg()
        self.is_connected = False
        self.last_ip_info = {}

proxy_manager = ProxyManager()
