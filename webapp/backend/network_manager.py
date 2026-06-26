import subprocess
from backend.logger import log

class MacOSNetworkManager:
    @staticmethod
    def bsd_to_logical(bsd_names: list[str]) -> list[str]:
        try:
            out = subprocess.check_output(["networksetup", "-listallhardwareports"]).decode()
            logical = []
            blocks = out.strip().split("\n\n")
            for block in blocks:
                lines = {}
                for l in block.splitlines():
                    if ": " in l:
                        k, _, v = l.partition(": ")
                        lines[k.strip()] = v.strip()
                        
                if lines.get("Device") in bsd_names:
                    logical.append(lines["Hardware Port"])
            return logical or ["Wi-Fi"]
        except Exception as e:
            log.error(f"Failed to map BSD to logical interfaces: {e}")
            return ["Wi-Fi"]

    @staticmethod
    def get_active_interfaces() -> list[str]:
        try:
            out = subprocess.check_output(["scutil", "--nwi"]).decode()
            active_bsd_names = [
                line.split()[0] for line in out.splitlines() 
                if "(Up," in line and "Loopback" not in line
            ]
            return MacOSNetworkManager.bsd_to_logical(active_bsd_names)
        except Exception as e:
            log.error(f"Failed to get active interfaces: {e}")
            return ["Wi-Fi"]

    @staticmethod
    def enable_proxy(port: int):
        active_interfaces = MacOSNetworkManager.get_active_interfaces()
        scripts = []
        for iface in active_interfaces:
            log.info(f"Enabling proxy on interface: {iface}")
            scripts.append(f"networksetup -setwebproxy '{iface}' 127.0.0.1 {port}")
            scripts.append(f"networksetup -setsecurewebproxy '{iface}' 127.0.0.1 {port}")
            scripts.append(f"networksetup -setwebproxystate '{iface}' on")
            scripts.append(f"networksetup -setsecurewebproxystate '{iface}' on")
            
        script_block = " && ".join(scripts)
        full_script = f'do shell script "{script_block}" with administrator privileges'
        try:
            subprocess.run(["osascript", "-e", full_script], check=True)
        except Exception as e:
            log.error(f"Failed to enable system proxy via osascript: {e}")

    @staticmethod
    def disable_proxy():
        active_interfaces = MacOSNetworkManager.get_active_interfaces()
        scripts = []
        for iface in active_interfaces:
            log.info(f"Disabling proxy on interface: {iface}")
            scripts.append(f"networksetup -setwebproxystate '{iface}' off")
            scripts.append(f"networksetup -setsecurewebproxystate '{iface}' off")
            
        script_block = " && ".join(scripts)
        full_script = f'do shell script "{script_block}" with administrator privileges'
        try:
            subprocess.run(["osascript", "-e", full_script], check=True)
        except Exception as e:
            log.error(f"Failed to disable system proxy via osascript: {e}")

    @staticmethod
    def preflight_cleanup():
        """Revert proxy if a previous SIGKILL (kill -9) crash bypassed atexit handlers."""
        log.info("Running preflight network cleanup...")
        for iface in MacOSNetworkManager.get_active_interfaces():
            try:
                out = subprocess.check_output(["networksetup", "-getwebproxy", iface]).decode()
                if "127.0.0.1" in out and "8118" in out and "Yes" in out:
                    log.warning(f"Found orphaned proxy on {iface}. Cleaning up...")
                    MacOSNetworkManager.disable_proxy()
                    break
            except Exception as e:
                log.error(f"Preflight cleanup error on {iface}: {e}")

net = MacOSNetworkManager()
