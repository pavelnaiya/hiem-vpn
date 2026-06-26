import os
import shutil
import subprocess
import platform
from pathlib import Path

# Paths
TAURI_BIN_DIR = Path("tauri-app/src-tauri/bin")
DYLIBS_DIR = TAURI_BIN_DIR / "dylibs"

def run_command(cmd, check=True):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()

def locate_binary(name):
    """Find a binary in standard locations."""
    paths_to_check = [
        shutil.which(name),
        f"/opt/homebrew/bin/{name}",
        f"/opt/homebrew/sbin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/local/sbin/{name}",
    ]
    for path in paths_to_check:
        if path and os.path.exists(path) and os.access(path, os.X_OK):
            print(f"Found {name} at {path}")
            return Path(path).resolve()
    
    raise RuntimeError(f"Could not locate {name}. Ensure it is installed via Homebrew.")

def get_dependencies(binary_path):
    """Run otool -L and return a list of dependency paths."""
    output = run_command(["otool", "-L", str(binary_path)])
    deps = []
    # Skip the first line as it's just the file name
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        # Format is usually: /path/to/lib.dylib (compatibility version X, current version Y)
        path = line.split(" (")[0].strip()
        deps.append(path)
    return deps

def is_system_library(path):
    """Check if the library is a core macOS system library."""
    # We shouldn't bundle anything in /usr/lib or /System/Library
    # We DO want to bundle /opt/homebrew or /usr/local
    return path.startswith("/usr/lib/") or path.startswith("/System/Library/")

def package_engines():
    print("Starting native engine bundling...")
    TAURI_BIN_DIR.mkdir(parents=True, exist_ok=True)
    DYLIBS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Locate binaries
    tor_src = locate_binary("tor")
    privoxy_src = locate_binary("privoxy")

    # 2. Copy binaries
    tor_dest = TAURI_BIN_DIR / "tor"
    privoxy_dest = TAURI_BIN_DIR / "privoxy"
    
    shutil.copy2(tor_src, tor_dest)
    shutil.copy2(privoxy_src, privoxy_dest)
    print("Copied executables.")

    # 3. Recursive Trace
    visited = set()
    queue = [tor_dest, privoxy_dest]
    dylib_mappings = {} # Original path -> bundled path
    
    while queue:
        current_file = queue.pop(0)
        
        # We need the real path if it's outside our bundled directory to read its deps correctly
        # But if it's already in our bundled directory, we just read it directly.
        # Actually, the file we are inspecting is in our bundled dir.
        
        deps = get_dependencies(current_file)
        
        for dep in deps:
            if is_system_library(dep) or dep.startswith("@executable_path") or dep.startswith("@loader_path"):
                continue
                
            # It's a non-system dependency (e.g. Homebrew). Resolve symlinks.
            real_dep_path = Path(dep).resolve()
            
            if real_dep_path not in visited:
                visited.add(real_dep_path)
                
                # 4. Copy Library
                lib_name = real_dep_path.name
                bundled_dep_path = DYLIBS_DIR / lib_name
                
                if not bundled_dep_path.exists():
                    shutil.copy2(real_dep_path, bundled_dep_path)
                    print(f"Copied dylib: {lib_name}")
                
                # Store the mapping from the original dependency path (as listed in otool) to the copied file's name
                # Note: multiple binaries might reference the same dylib via different symlinks, but it ultimately resolves to real_dep_path.
                # So we must map the *literal text* found in `otool -L` to the bundled filename.
                
                queue.append(bundled_dep_path)
                
            # Record mapping for patching
            if current_file not in dylib_mappings:
                dylib_mappings[current_file] = []
            dylib_mappings[current_file].append((dep, real_dep_path.name))

    # 5. Patch (Copies Only)
    print("Patching dependency paths...")
    for file_to_patch, mappings in dylib_mappings.items():
        # Make file writable if it isn't (sometimes dylibs are read-only)
        os.chmod(file_to_patch, 0o755)
        
        for original_path, new_name in mappings:
            # For dylibs in the frameworks folder, @loader_path works.
            # For executables in MacOS folder, @executable_path/../Frameworks/ works.
            if file_to_patch.parent == DYLIBS_DIR:
                new_path = f"@loader_path/{new_name}"
            else:
                new_path = f"@executable_path/../Frameworks/{new_name}"
                
            run_command(["install_name_tool", "-change", original_path, new_path, str(file_to_patch)])
            
        # If it's a dylib, also change its ID
        if file_to_patch.suffix == '.dylib':
            run_command(["install_name_tool", "-id", f"@loader_path/{file_to_patch.name}", str(file_to_patch)])

    # 6. Verify Paths
    print("Verifying paths...")
    for file_to_patch in dylib_mappings.keys():
        deps = get_dependencies(file_to_patch)
        for dep in deps:
            if not is_system_library(dep) and not dep.startswith("@loader_path") and not dep.startswith("@executable_path"):
                raise RuntimeError(f"Failed to patch {dep} in {file_to_patch}")

    # 7. Sign & Verify
    print("Re-signing binaries...")
    all_files = list(dylib_mappings.keys())
    for f in all_files:
        run_command(["codesign", "--force", "--sign", "-", str(f)])
        run_command(["codesign", "--verify", str(f)])

    # 8. Smoke Test (Skipped)
    print("Skipping Smoke Test (binaries are configured for macOS .app bundle structure)")

    # 9. Stage
    machine = platform.machine().lower()
    if machine == "arm64":
        machine = "aarch64"
    target = f"{machine}-apple-darwin"
    
    tor_final = TAURI_BIN_DIR / f"tor-{target}"
    privoxy_final = TAURI_BIN_DIR / f"privoxy-{target}"
    
    if tor_final.exists():
        tor_final.unlink()
    if privoxy_final.exists():
        privoxy_final.unlink()
        
    tor_dest.rename(tor_final)
    privoxy_dest.rename(privoxy_final)
    
    # 10. Update tauri.conf.json frameworks array
    print("Updating tauri.conf.json macOS frameworks...")
    import json
    tauri_conf_path = Path("tauri-app/src-tauri/tauri.conf.json")
    with open(tauri_conf_path, "r") as f:
        tauri_conf = json.load(f)
        
    # Get all bundled dylibs
    bundled_dylibs = [f"bin/dylibs/{f.name}" for f in DYLIBS_DIR.iterdir() if f.is_file() and f.name.endswith(".dylib")]
    
    if "bundle" not in tauri_conf:
        tauri_conf["bundle"] = {}
    if "macOS" not in tauri_conf["bundle"]:
        tauri_conf["bundle"]["macOS"] = {}
        
    tauri_conf["bundle"]["macOS"]["frameworks"] = bundled_dylibs
    
    # Clean up old generic resources entry if it exists
    if "resources" in tauri_conf["bundle"]:
        tauri_conf["bundle"]["resources"] = [r for r in tauri_conf["bundle"]["resources"] if not r.startswith("bin/dylibs/")]
        
    with open(tauri_conf_path, "w") as f:
        json.dump(tauri_conf, f, indent=2)
    
    print(f"Successfully staged binaries for {target}!")

if __name__ == "__main__":
    package_engines()
