import os
import signal
import subprocess
import shutil
import time
import re
import stem
from stem.control import Controller
from stem import Signal
from backend.logger import log
from backend.event_bus import event_bus
from backend.config_generator import TORRC_PATH, PRIVOXY_CONF_PATH, TOR_CONTROL_PORT

class TorController:
    def __init__(self):
        self.tor_proc = None
        self.privoxy_proc = None
        self.pgrp = None

    def spawn(self):
        log.info("Spawning Tor and Privoxy engines...")
        tor_bin = shutil.which("tor") or "/opt/homebrew/bin/tor"
        privoxy_bin = shutil.which("privoxy") or "/opt/homebrew/bin/privoxy"
        
        if not os.path.exists(tor_bin):
            raise FileNotFoundError(f"Tor binary not found at {tor_bin}")
        if not os.path.exists(privoxy_bin):
            raise FileNotFoundError(f"Privoxy binary not found at {privoxy_bin}")

        # Spawn both processes in their own sessions so they don't die if the parent dies unexpectedly
        self.tor_proc = subprocess.Popen([tor_bin, "-f", TORRC_PATH], start_new_session=True)
        self.privoxy_proc = subprocess.Popen([privoxy_bin, "--no-daemon", PRIVOXY_CONF_PATH], start_new_session=True)
        log.info("Engines spawned successfully.")

    def wait_for_bootstrap(self, timeout=120):
        log.info("Waiting for Tor to bootstrap...")
        deadline = time.time() + timeout
        ctrl = None
        
        # Retry loop to avoid race condition where Tor hasn't bound the ControlPort yet
        while time.time() < deadline:
            try:
                ctrl = Controller.from_port(port=TOR_CONTROL_PORT)
                ctrl.authenticate()  # Cookie auth
                break
            except Exception:
                time.sleep(0.5)
                
        if ctrl is None:
            raise TimeoutError("Tor ControlPort never opened")
            
        # Poll for 100% bootstrap
        while time.time() < deadline:
            bsp = ctrl.get_info("status/bootstrap-phase")
            match = re.search(r"PROGRESS=(\d+)", str(bsp))
            if match:
                progress = int(match.group(1))
                event_bus.push({"type": "bootstrap", "progress": progress})
                if progress >= 100:
                    log.info("Tor bootstrap reached 100%")
                    return
            time.sleep(1)
            
        raise TimeoutError("Tor did not bootstrap within timeout")

    def killpg(self):
        if self.tor_proc:
            log.info("Terminating Tor...")
            try:
                self.tor_proc.kill()
            except Exception:
                pass
            self.tor_proc = None
            
        if self.privoxy_proc:
            log.info("Terminating Privoxy...")
            try:
                self.privoxy_proc.kill()
            except Exception:
                pass
            self.privoxy_proc = None

    def rotate_ip(self):
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
                ctrl.authenticate()
                ctrl.signal(Signal.NEWNYM)
            log.info("Requested new Tor identity (IP rotation).")
            return True
        except Exception as e:
            log.error(f"Failed to rotate Tor IP: {e}")
            return False

tor = TorController()
