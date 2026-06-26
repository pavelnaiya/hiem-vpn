# Native Mac Engine Bundling (Standalone App)

## Objective
To remove the Homebrew (`brew install tor privoxy`) dependency for macOS users, allowing Hiem VPN to act as a truly standalone desktop application.

## Assumptions & Limitations
* This packager targets Homebrew-installed Tor and Privoxy on macOS.
* It must be executed on the same architecture as the binaries being bundled (Apple Silicon → Apple Silicon, Intel → Intel).
* System libraries provided by macOS are intentionally excluded from bundling.
* The generated bundle is intended for redistribution on machines of the same architecture.
* If Homebrew changes dependency layouts in future releases, the recursive dependency discovery will automatically adapt, but the smoke test acts as the final validation.

## The Problem
Tor and Privoxy compiled by Homebrew are dynamically linked. They rely on external shared libraries (`.dylib` files) located in `/opt/homebrew/lib/` or `/usr/local/lib/` (such as `libevent`, `libssl`, `libpcre2`). If we simply copy the `tor` binary to another Mac without Homebrew, it will crash on launch because those `.dylib` files are missing.

## The Solution: Automated `dylib` Bundling
We will automate the extraction of Homebrew's binaries and their dependencies using macOS's built-in `otool` and `install_name_tool`.

### Step 1: The Packager Script
We will create a non-interactive, CI-friendly Python script (`scripts/bundle_mac_engines.py`) that performs the following steps:

1. **Locate**: Find `tor` and `privoxy` by checking `shutil.which()`, followed by `/opt/homebrew/bin/` and `/usr/local/bin/`. Fail with a clear error if not found.
2. **Extract**: Copy the `tor` and `privoxy` binaries into `tauri-app/src-tauri/bin/`, strictly preserving their executable permissions.
3. **Recursive Trace**: Use a queue algorithm with `otool -L` and a `visited` set to recursively find all non-system dependencies, preventing duplicate work from circular library references. Resolve any symlink chains (e.g., `libssl.dylib -> libssl.3.dylib`) using `os.path.realpath()` to ensure only the actual files are tracked and copied.
4. **Bundle**: Copy all resolved `.dylib` files into `tauri-app/src-tauri/bin/dylibs/`.
5. **Patch**: Rewrite all non-system dependency references in the copied binaries and libraries to relative `@loader_path` paths so the application is completely independent of Homebrew installation directories.
6. **Verify Paths**: Run `otool -L` to verify the rewritten dependency paths.
7. **Sign & Verify**: Re-sign all modified executables and libraries using `codesign --force --sign -`, followed by verifying the signatures with `codesign --verify`.
8. **Smoke Test**: Execute `./tor --version` and `./privoxy --version` on the patched binaries to confirm they run without "Library not loaded" errors. If either fails, the packaging process fails immediately.
9. **Stage**: Stage the binaries using Tauri's architecture-specific sidecar naming convention based on `platform.machine()`:
   - `tor-aarch64-apple-darwin` or `tor-x86_64-apple-darwin`
   - `privoxy-aarch64-apple-darwin` or `privoxy-x86_64-apple-darwin`

### Step 2: Rust/Tauri Integration
Rust will be the single source of truth for native executable discovery.
1. Tauri's `src-tauri/src/main.rs` will resolve the bundled paths for Tor and Privoxy using Tauri's sidecar API.
2. Rust will inject these absolute paths into the Python sidecar via environment variables (`TOR_PATH` and `PRIVOXY_PATH`).

### Step 3: Update Python Backend
The Python backend (`tor_controller.py`) will know absolutely nothing about OS specifics, Tauri, or bundle layouts. It simply receives paths from the environment:
```python
tor_bin = os.environ.get("TOR_PATH")
if not tor_bin:
    raise RuntimeError("TOR_PATH not provided by environment")

privoxy_bin = os.environ.get("PRIVOXY_PATH")
# ...
```

### Step 4: Update Tauri Configuration
Modify `tauri-app/src-tauri/tauri.conf.json` to include the newly bundled binaries in the `bundle.externalBin` array. This ensures Tauri automatically signs the binaries and includes them in the final `.app` package.
