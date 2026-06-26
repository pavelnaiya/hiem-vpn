# Native Mac Engine Bundling (Standalone App)

## Objective
To remove the Homebrew (`brew install tor privoxy`) dependency for macOS users, allowing Hiem VPN to act as a truly standalone desktop application.

## The Problem
Tor and Privoxy compiled by Homebrew are dynamically linked. They rely on external shared libraries (`.dylib` files) located in `/opt/homebrew/lib/` (such as `libevent`, `libssl`, `libpcre2`). If we simply copy the `tor` binary to another Mac without Homebrew, it will crash on launch because those `.dylib` files are missing.

While the Tor Project provides a static "Expert Bundle" for macOS, Privoxy does not provide an official pre-compiled standalone binary for modern Macs (Apple Silicon).

## The Solution: Automated `dylib` Bundling
Rather than attempting to compile Privoxy from scratch, we will automate the extraction of Homebrew's binaries and their dependencies using macOS's built-in `otool` and `install_name_tool`.

### Step 1: The Packager Script
We will create a Python script (`scripts/bundle_mac_engines.py`) that performs the following steps in under a second:

1. **Extract**: Copy the `tor` and `privoxy` binaries from `/opt/homebrew/bin/` into `tauri-app/src-tauri/bin/`.
2. **Trace**: Use `otool -L` on both binaries to find any `.dylib` dependencies that are NOT core system libraries (i.e., anything located in `/opt/homebrew/`).
3. **Bundle**: Copy those specific `.dylib` files into `tauri-app/src-tauri/bin/dylibs/`.
4. **Patch**: Use `install_name_tool -change` to modify the internal headers of `tor` and `privoxy` so they look for their libraries in `@executable_path/dylibs/` instead of `/opt/homebrew/`.
5. **Format**: Rename the binaries to match Tauri's sidecar target naming convention:
   - `tor-aarch64-apple-darwin`
   - `privoxy-aarch64-apple-darwin`

### Step 2: Update Python Backend
The Python backend (`tor_controller.py`) currently has hardcoded paths:
```python
tor_bin = "/opt/homebrew/bin/tor"
privoxy_bin = "/opt/homebrew/sbin/privoxy"
```
This will be updated to:
1. Check if the backend is running as a compiled Sidecar (`getattr(sys, 'frozen', False)`).
2. If compiled, use the bundled binaries residing in the same directory (`sys._MEIPASS` or `os.path.dirname(sys.executable)`).
3. Fallback to Homebrew paths only during local development.

### Step 3: Update Tauri Configuration
Modify `tauri-app/src-tauri/tauri.conf.json` to include the newly bundled binaries in the `bundle.externalBin` array. This ensures Tauri automatically signs the binaries and includes them in the final `.app` package.

## Conclusion
This approach guarantees that the binaries perfectly match the target architecture without the massive overhead of setting up a C-compilation toolchain for Privoxy, resulting in a zero-dependency standalone Mac app.
