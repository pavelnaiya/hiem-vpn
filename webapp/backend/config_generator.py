import os
import subprocess
from backend.logger import log
from backend.settings_manager import settings_manager

HIEM_DIR = os.path.expanduser("~/.hiem")
TORRC_PATH = os.path.join(HIEM_DIR, "torrc")
PRIVOXY_CONF_PATH = os.path.join(HIEM_DIR, "privoxy_config")
TOR_CONTROL_PORT = 9051

class ConfigRenderer:
    @staticmethod
    def render_immutable_configs():
        log.info("Rendering immutable configs...")
        profile = settings_manager.settings.active_profile
        
        # Generate torrc
        with open(TORRC_PATH, "w") as f:
            f.write(f"SocksPort 9050\nControlPort {TOR_CONTROL_PORT}\n")
            f.write(f"CookieAuthentication 1\nCookieAuthFile {os.path.join(HIEM_DIR, 'tor_cookie')}\n")
            if profile.exit_node != "Any":
                f.write(f"ExitNodes {{{profile.exit_node.lower()}}}\nStrictNodes 1\n")

        # Generate Privoxy
        with open(PRIVOXY_CONF_PATH, "w") as f:
            f.write("listen-address  127.0.0.1:8118\ntoggle  1\nenable-remote-toggle  0\nenable-remote-http-toggle  0\nenable-edit-actions 0\nenforce-blocks 0\nbuffer-limit 4096\nenable-proxy-authentication-forwarding 0\nforwarded-connect-retries  0\naccept-intercepted-requests 0\nallow-cgi-request-crunching 0\nsplit-large-forms 0\nkeep-alive-timeout 5\ntolerate-pipelining 1\nsocket-timeout 300\n")
            f.write("\n# --- SMART ROUTING START ---\n")
            
            if profile.routing_mode == "all":
                f.write("forward-socks5t / 127.0.0.1:9050 .\n")
            elif profile.routing_mode == "whitelist":
                f.write("forward / .\n")
                # Force ip-api.com over Tor to resolve the Tor exit node IP correctly
                f.write("forward-socks5t .ip-api.com 127.0.0.1:9050 .\n")
                for d in [d.strip() for d in profile.routing_domains.split(",") if d.strip()]:
                    f.write(f"forward-socks5t .{d} 127.0.0.1:9050 .\n")
            elif profile.routing_mode == "blacklist":
                f.write("forward-socks5t / 127.0.0.1:9050 .\n")
                for d in [d.strip() for d in profile.routing_domains.split(",") if d.strip()]:
                    if "ip-api.com" not in d:
                        f.write(f"forward .{d} .\n")
                        
            f.write("# --- SMART ROUTING END ---\n")
        log.info("Configs rendered successfully.")

config = ConfigRenderer()
