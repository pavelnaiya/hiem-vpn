import time
import asyncio
from backend.logger import log
from backend.fsm import fsm, ProxyState
from backend.proxy_manager import proxy_manager
from backend.tor_controller import tor
from backend.event_bus import event_bus

class ConnectionService:
    def connect(self):
        if not fsm.transition(ProxyState.CONNECTING):
            return False
            
        try:
            fsm.transition(ProxyState.BOOTSTRAPPING, force=True)
            proxy_manager.start_engines()
            fsm.transition(ProxyState.CONNECTED, force=True)
            
            # Broadcast state
            event_bus.push({
                "type": "status",
                "status": "Working",
                "ip": proxy_manager.last_ip_info.get("query", "Unknown"),
                "countryCode": proxy_manager.last_ip_info.get("countryCode", ""),
                "country": proxy_manager.last_ip_info.get("country", "Unknown")
            })
            return True
        except Exception as e:
            log.error(f"Connection failed: {e}")
            fsm.transition(ProxyState.ERROR, force=True)
            proxy_manager.stop_engines() # Revert
            event_bus.push({"type": "error", "message": str(e)})
            return False

    def disconnect(self):
        if not fsm.transition(ProxyState.DISCONNECTING):
            # If we're already disconnected or error, just ensure engines are dead
            proxy_manager.stop_engines()
            fsm.transition(ProxyState.DISCONNECTED, force=True)
            return True
            
        try:
            proxy_manager.stop_engines()
            fsm.transition(ProxyState.DISCONNECTED, force=True)
            event_bus.push({"type": "status", "status": "Disconnected"})
            return True
        except Exception as e:
            log.error(f"Disconnect failed: {e}")
            fsm.transition(ProxyState.ERROR, force=True)
            return False

    def rotate_identity(self):
        if fsm.current_state() == ProxyState.CONNECTED:
            if tor.rotate_ip():
                time.sleep(3) # Wait for rotation to propagate through Tor network
                proxy_manager.fetch_ip_info()
                event_bus.push({
                    "type": "status",
                    "status": "Working",
                    "ip": proxy_manager.last_ip_info.get("query", "Unknown"),
                    "countryCode": proxy_manager.last_ip_info.get("countryCode", ""),
                    "country": proxy_manager.last_ip_info.get("country", "Unknown")
                })
                return True
        return False

connection_service = ConnectionService()

async def health_monitor_loop():
    """Monitors engine health and drives recovery if processes die unexpectedly."""
    while True:
        if fsm.current_state() == ProxyState.CONNECTED:
            if tor.tor_proc and tor.tor_proc.poll() is not None:
                log.error("Tor process died unexpectedly!")
                fsm.transition(ProxyState.ERROR, force=True)
                proxy_manager.stop_engines()
                event_bus.push({"type": "error", "message": "Tor process crashed unexpectedly."})
            elif tor.privoxy_proc and tor.privoxy_proc.poll() is not None:
                log.error("Privoxy process died unexpectedly!")
                fsm.transition(ProxyState.ERROR, force=True)
                proxy_manager.stop_engines()
                event_bus.push({"type": "error", "message": "Privoxy process crashed unexpectedly."})
        await asyncio.sleep(5)
