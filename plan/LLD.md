# Low-Level Design (LLD) & Code Blueprint: Hiem

## 1. Tauri Configuration & Project Setup

### 1.1 `tauri.conf.json` Setup
Tauri is configured to bundle and spawn the compiled Python FastAPI backend as an `externalBin` sidecar.

```json
{
  "build": {
    "frontendDist": "../src"
  },
  "app": {
    "withGlobalTauri": true
  },
  "bundle": {
    "active": true,
    "externalBin": [
      "bin/python-backend"
    ]
  }
}
```

## 2. Tauri Core (Rust) Backend
The Rust core initializes necessary plugins, spawns the sidecar, actively monitors the child process, and restarts it if it crashes **up to a maximum bound** to avoid infinite crash loops.

### 2.1 `src-tauri/src/lib.rs` (Bounded Backoff Restart Strategy)
```rust
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandEvent, CommandChild};
use std::sync::Mutex;
use tauri::Manager;
use tokio::time::{sleep, Duration};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init()) 
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let app_handle = app.handle().clone();
            
            tauri::async_runtime::spawn(async move {
                let mut crash_count = 0;
                let max_restarts = 5;
                
                loop {
                    let sidecar_command = app_handle.shell().sidecar("python-backend").unwrap();
                    let (mut rx, child) = sidecar_command.spawn().expect("Failed to spawn sidecar");
                    
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Terminated(_) | CommandEvent::Error(_) => {
                                crash_count += 1;
                                app_handle.emit("backend-crashed", crash_count).unwrap();
                                break;
                            },
                            _ => {}
                        }
                    }
                    
                    if crash_count >= max_restarts {
                        app_handle.emit("backend-fatal", ()).unwrap();
                        break; // Stop restarting, surface hard error to UI
                    }
                    sleep(Duration::from_secs(3)).await;
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### 2.2 Frontend SSE Reconnect Logic
```javascript
import { listen } from '@tauri-apps/api/event';

listen('backend-crashed', (event) => {
    console.warn(`Backend crashed (${event.payload} times). Waiting for Rust core to respawn sidecar...`);
    setTimeout(connectEventSource, 4000); 
});

listen('backend-fatal', () => {
    showFatalErrorOverlay("The proxy engine has crashed continuously and cannot be restarted. Please check the logs.");
});
```

---

## 3. Python FastAPI Sidecar (Modularized Architecture)

The backend (`main.py`) acts solely as the HTTP glue for several focused modules rather than being a God Object. It binds strictly to `127.0.0.1`.

### 3.1 `settings_manager.py` (Persistent Settings)
```python
import json, os

HIEM_DIR = os.path.expanduser("~/.hiem")
SETTINGS_FILE = os.path.join(HIEM_DIR, "settings.json")
LOG_FILE = os.path.join(HIEM_DIR, "app.log")

class SettingsManager:
    # Handles loading/saving profiles and settings natively
    pass
```

### 3.2 `event_bus.py` (SSE Broadcaster & Heartbeat)
```python
import asyncio, json
from typing import Set

class EventBus:
    def __init__(self):
        self.subscribers: Set[asyncio.Queue] = set()
        self.loop = None
        
    def push(self, data: dict):
        if self.loop and not self.loop.is_closed():
            async def _broadcast():
                for q in list(self.subscribers):
                    await q.put(data)
            asyncio.run_coroutine_threadsafe(_broadcast(), self.loop)
```

### 3.3 `fsm.py` (Explicit State Machine)
```python
from enum import Enum

class ProxyState(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    BOOTSTRAPPING = "Bootstrapping"
    CONNECTED = "Connected"
    DISCONNECTING = "Disconnecting"
    ERROR = "Error"
    
# Invalid transitions (e.g. Connected -> Bootstrapping) are blocked here.
```

### 3.4 `network_manager.py` (Cross-Platform OS Abstraction)
```python
class NetworkManager:
    """Interface for system-level proxy adjustments."""
    def enable_proxy(self, port: int): pass
    def disable_proxy(self): pass
    def get_active_interfaces(self) -> list[str]: pass
    def preflight_cleanup(self): pass
```
An explicit `MacOSNetworkManager` inherits this and implements `osascript` / `scutil`.

### 3.5 `tor_controller.py` & `config_generator.py`
- `ConfigGenerator`: Renders immutable templates for `torrc` and `privoxy_config` once on connect.
- `TorController`: Spawns the processes inside an `os.setsid()` UNIX session, handles Cookie Authentication, and polls `status/bootstrap-phase`.

### 3.6 `proxy_manager.py` (Lifecycle Orchestrator)
Orchestrates the explicit connect and disconnect sequences.

```python
class ProxyManager:
    def connect(self):
        fsm.transition(ProxyState.CONNECTING)
        config.render_immutable_configs()
        tor.spawn()
        fsm.transition(ProxyState.BOOTSTRAPPING)
        tor.wait_for_bootstrap()
        fsm.transition(ProxyState.CONNECTED)
        net.enable_proxy(8118)
        
    def disconnect(self):
        fsm.transition(ProxyState.DISCONNECTING)
        net.disable_proxy()
        tor.killpg()
        fsm.transition(ProxyState.DISCONNECTED)
```

### 3.7 `main.py` (FastAPI Entrypoint)
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    event_bus.loop = asyncio.get_running_loop()
    # Start health monitor background task
    asyncio.create_task(health_monitor_loop())
    # Start heartbeat ping task
    asyncio.create_task(heartbeat_loop())
    net_manager.preflight_cleanup()
    yield
    # Shutdown sequence
    proxy_manager.disconnect()

app = FastAPI(lifespan=lifespan)
```

---

## 4. Build and Deployment Checklist

1. **Compile Python Backend (Multi-Arch Requirement)**: 
   *Note: PyInstaller cannot cross-compile. A CI pipeline (e.g., GitHub Actions) must build these natively on `macos-latest` (ARM) and `macos-13` (Intel), OR you must build on two physical machines and stitch them together into a universal binary using `lipo`.*
   ```bash
   pyinstaller --onefile --name python-backend-aarch64-apple-darwin main.py
   ```
2. **Move Binaries to Tauri Bin**: Place both compiled python binaries into `tauri-app/src-tauri/bin/`.
3. **Build Tauri App**: 
   ```bash
   npm run tauri build
   ```
4. **Output**: Produces a `Hiem.app` supporting both architectures.
