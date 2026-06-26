# Hiem VPN - Future Roadmap (Standalone App)

This document outlines the strategic path for evolving Hiem VPN from a macOS-centric, Homebrew-dependent tool into a truly universal, zero-dependency standalone desktop application for macOS, Windows, and Linux.

## Phase 1: Zero-Dependency Architecture (Native Binaries)
The current limitation is the reliance on system package managers (Homebrew) for the `tor` and `privoxy` engines. The goal is a true "download-and-click" experience.

1. **Bundle Engines as Tauri Sidecars**
   - Download the official pre-compiled `.exe`, `.app`, and ELF binaries for Tor and Privoxy for all major architectures (x86_64, aarch64).
   - Place them in `tauri-app/src-tauri/bin/` alongside the Python backend.
   - Configure `tauri.conf.json` to bundle these engines native to the OS.
2. **Dynamic Path Resolution**
   - Refactor `tor_controller.py` to stop hardcoding `/opt/homebrew/bin/tor`.
   - The Python backend must dynamically resolve the path to the bundled Tor/Privoxy binaries relative to its own execution path (`sys._MEIPASS` or Tauri's resource directory).

## Phase 2: Cross-Platform System Integration
The current proxy injection relies entirely on macOS's `networksetup` and `osascript`. We need OS-agnostic network adapters.

1. **Windows Support (`network_manager.py`)**
   - Implement `winreg` Python scripts to dynamically edit `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings` for global proxy routing.
   - Adapt process management (`tor_controller.py`) to use Windows process groups instead of UNIX `killpg()`.
2. **Linux Support (`network_manager.py`)**
   - Implement GTK/GNOME `gsettings` integration for proxy settings.
   - Fallback to modifying `/etc/environment` for headless/non-GTK setups.
3. **Privilege Escalation Abstraction**
   - Replace macOS `osascript` with a universal privilege escalation flow (e.g., Tauri's native command execution with sudo prompts, or running the Python backend as a system service).

## Phase 3: Advanced Routing & Kill Switch Implementation
The UI currently has placeholders for advanced features that need backend implementations.

1. **Auto-Kill Switch**
   - If Tor dies unexpectedly, the system proxy must either immediately switch to a blocked state or null-route traffic.
   - Use `pfctl` (macOS), `Windows Firewall Rules` (Windows), or `iptables` (Linux) to drop all non-local packets until Tor is restored.
2. **Smart Split Tunneling**
   - Implement the "Bypass VPN" (Blacklist) and "Split Tunneling" (Whitelist) logic.
   - This requires dynamically writing routing rules to the `privoxy` configuration file based on the user's UI selections before spawning the Privoxy engine.
3. **Auto-Launch on Public WiFi**
   - Poll the system for network SSID changes (using macOS `airport` or Windows `netsh WLAN`).
   - Auto-trigger the FSM to `CONNECTING` if the network is deemed unsecured.

## Phase 4: Production Release & CI/CD
1. **GitHub Actions Workflow**
   - Set up cross-compilation matrix (macOS, Windows, Ubuntu).
   - Automatically compile the Python FastAPI Sidecar via PyInstaller on all OS runners.
   - Automatically trigger `tauri build` and generate `.dmg` (Mac), `.msi` (Windows), and `.AppImage` (Linux) artifacts on every Git Release.
2. **App Signing and Notarization**
   - Apple Developer Certificate signing for the `.dmg` to bypass the "unidentified developer" warning.
   - Windows Authenticode signing for the `.exe`.
