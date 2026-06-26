# High Level Design (HLD): Hiem - Consumer VPN Proxy Manager

## 1. Executive Summary
This document outlines the detailed architecture for Hiem, a lightweight, native, cross-platform desktop proxy manager application. Hiem is designed to look and feel like a premium consumer VPN while acting as a highly configurable proxy router (Tor + Privoxy) for privacy and web scraping.

Instead of heavy electron wrappers or overly complex macOS-specific Swift daemons, this project utilizes a **Tauri + Python Sidecar** architecture. This ensures an ultra-lightweight memory footprint while managing complex proxy routing logic seamlessly.

---

## 2. System Architecture (Tauri + Python Process Manager)

The architecture relies on Tauri's rust-based native webview for the UI, bundling a FastAPI server as a hidden child process (Sidecar). The Python Sidecar acts as a robust **Process Manager** that dynamically spawns and terminates the underlying proxy engines (Tor and Privoxy) based on user interaction.

```mermaid
graph TD
    subgraph Tauri App Window (Native OS)
        UI[Vanilla HTML/CSS/JS SPA]
        RustCore[Tauri Rust Core]
        UI <-->|HTTP + Bearer Token| Sidecar
        UI <-->|Tauri IPC| RustCore
    end

    subgraph Sidecar (Hidden Child Process)
        Sidecar[Python FastAPI]
        PM[ProcessManager]
        Net[NetworkManager]
        Tor[TorController]
        State[Finite State Machine]
        Config[ConfigRenderer]
        
        Sidecar --> PM
        Sidecar --> State
        PM --> Tor
        PM --> Config
        State --> Net
    end
    
    subgraph Engine Processes (Ephemeral)
        Privoxy[Privoxy Routing Engine]
        TorNet[Tor Network]
    end

    subgraph macOS System
        SysNet[macOS Network Preferences]
    end

    RustCore -->|Spawn on Launch & Monitor| Sidecar
    Net -->|osascript Admin Prompt| SysNet
    
    PM -->|Spawn/Kill & ControlPort| TorNet
    PM -->|Spawn/Kill| Privoxy

    Privoxy -->|SOCKS5| TorNet
```

---

## 3. Technology Stack & Architectural Principles
- **Frontend**: Vanilla HTML/JS/CSS built as a Single Page Application (SPA).
- **Desktop Wrapper**: Tauri v2 (Rust-based). Rust monitors the sidecar with a **Bounded Backoff Restart Strategy** to prevent endless crash loops, surfacing hard failures to the UI.
- **Backend / Sidecar**: Python + FastAPI. The HTTP layer is retained to support future CLI automation, browser extensions, and programmatic integrations.
- **Modular Python Architecture**: The sidecar is heavily modularized to prevent a "God Object", splitting logic into `NetworkManager`, `TorController`, `ConfigRenderer`, and a robust `Finite State Machine`.
- **System Automation**: Cross-platform abstraction interface (e.g. `NetworkManager`) with an explicit macOS backend implemented via `osascript` and `scutil`.

---

## 4. Core Components Detailed Design

### 4.1 The Frontend UI & State Machine
- **Layout**: Minimalist "Home" screen and "Settings" layout.
- **State Management (SSE)**: The UI connects to a **Server-Sent Events (SSE)** stream (`/api/events`). The stream pushes explicit FSM transitions (`Disconnected` -> `Connecting` -> `Bootstrapping` -> `Connected`) and includes a 30s heartbeat ping to prevent idle connection drops.

### 4.2 The Python Sidecar (Modularized)
- **Deployment**: Compiled into standalone binaries using PyInstaller.
- **Security (API Token)**: Secured via `127.0.0.1` binding and a dynamically generated Bearer token (`~/.hiem/api_token`).
- **Persistent Data & Logging**: Settings, profiles, state, and logs are persisted explicitly in `~/.hiem/` (e.g., `settings.json`, `app.log`).
- **Dynamic Process Lifecycle**: Spawned dynamically via `subprocess.Popen` inside a managed **UNIX session via `os.setsid()`**.
- **Immutable Configuration**: Configurations (`torrc`, `privoxy_config`) are rendered via templates on connect and never mutated during runtime.

### 4.3 The Smart Routing Engine (Privoxy)
Acts as the central traffic director mapping HTTP requests. Depending on the settings, Privoxy routes specified target domains anonymously through Tor.

---

## 5. Security & Reliability Fail-Safes

- **Guaranteed Proxy Cleanup**: Best-effort graceful cleanup using `signal.SIGTERM` handlers and a defined disconnect sequence, combined with strict **Startup Reconciliation (Pre-flight checks)** that restore a clean networking state after ungraceful termination (e.g., `kill -9` or kernel panics).
- **Orphan Process Eradication**: Because the child engines (Tor/Privoxy) are spawned inside a dedicated UNIX session, terminating the sidecar allows it to cleanly `killpg()` the entire tree.
- **Synchronized Bootstrapping & Health Monitoring**: The Sidecar verifies via Tor's ControlPort that Tor has reached `100% Bootstrap Progress` before enabling proxies. A background health monitor continuously verifies that engines are alive and ports are bound.
- **Dynamic Network Interface Mapping**: The macOS `NetworkManager` natively parses `scutil --nwi` to determine the primary active network interface and targets proxy settings accurately to prevent traffic leaks across secondary interfaces.
