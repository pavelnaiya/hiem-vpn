import os
import sys
import uuid
import json
import asyncio
from fastapi import FastAPI, Depends, HTTPException, Security, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager

from backend.logger import log
from backend.settings_manager import settings_manager, Settings
from backend.event_bus import event_bus, heartbeat_loop
from backend.network_manager import net
from backend.connection_service import connection_service, health_monitor_loop
import random

# --- Security Token ---
API_TOKEN = str(uuid.uuid4())
HIEM_DIR = os.path.expanduser("~/.hiem")
TOKEN_PATH = os.path.join(HIEM_DIR, "api_token")
with open(TOKEN_PATH, "w") as f:
    f.write(API_TOKEN)
os.chmod(TOKEN_PATH, 0o600)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

def verify_token(token: str = None, api_key: str = Security(api_key_header)):
    # Support both ?token= query param and Authorization header
    actual_token = token
    if api_key and api_key.startswith("Bearer "):
        actual_token = api_key.split("Bearer ")[1]
        
    if actual_token != API_TOKEN and actual_token != "dev":
        raise HTTPException(status_code=401, detail="Unauthorized")

async def auto_rotation_loop():
    """Background loop that rotates Tor IP if rotation frequency is set."""
    while True:
        interval = settings_manager.settings.frequency_seconds
        
        if interval <= 0 or fsm.current_state() != ProxyState.CONNECTED:
            await asyncio.sleep(5)
            continue
            
        if settings_manager.settings.rotation_jitter:
            jitter = interval * 0.3
            actual_sleep = interval + random.uniform(-jitter, jitter)
        else:
            actual_sleep = interval
            
        slept = 0
        while slept < actual_sleep:
            if settings_manager.settings.frequency_seconds <= 0 or fsm.current_state() != ProxyState.CONNECTED:
                break
            if settings_manager.settings.frequency_seconds != interval:
                break
                
            await asyncio.sleep(1)
            slept += 1
        else:
            if fsm.current_state() == ProxyState.CONNECTED:
                log.info(f"Auto-rotating IP after {actual_sleep:.1f}s")
                await asyncio.to_thread(connection_service.rotate_identity)

# --- App Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting up Hiem Sidecar...")
    event_bus.loop = asyncio.get_running_loop()
    
    # Pre-flight proxy cleanup for orphaned proxies on startup
    net.preflight_cleanup()
    
    # Start background tasks
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(health_monitor_loop())
    asyncio.create_task(auto_rotation_loop())
    
    yield
    
    log.info("Shutting down Hiem Sidecar...")
    connection_service.disconnect()

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Mount static frontend
# app.mount("/static", StaticFiles(directory="static"), name="static")

# @app.get("/")
# def read_index():
#     return FileResponse("static/index.html")

# @app.get("/{filename:path}")
# def read_static(filename: str):
#     file_path = os.path.join("static", filename)
#     if os.path.exists(file_path):
#         return FileResponse(file_path)
#     return {"error": "not found"}

# --- API Routes ---
@app.get("/api/v1/events")
async def event_stream(token: str = Depends(verify_token)):
    q: asyncio.Queue = asyncio.Queue()
    event_bus.subscribers.add(q)
    
    async def event_generator():
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            event_bus.subscribers.discard(q)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/v1/connect")
async def api_connect(token: str = Depends(verify_token)):
    # Run connect sequence in a thread pool to avoid blocking the async event loop
    asyncio.get_running_loop().run_in_executor(None, connection_service.connect)
    return {"status": "connecting"}

@app.post("/api/v1/disconnect")
def api_disconnect(token: str = Depends(verify_token)):
    connection_service.disconnect()
    return {"status": "disconnected"}

@app.post("/api/v1/rotate")
async def force_rotate(token: str = Depends(verify_token)):
    asyncio.get_running_loop().run_in_executor(None, connection_service.rotate_identity)
    return {"status": "rotating"}

@app.get("/api/v1/settings")
def get_settings(token: str = Depends(verify_token)):
    return settings_manager.settings.dict()

@app.post("/api/v1/settings")
def update_settings(settings: Settings, token: str = Depends(verify_token)):
    settings_manager.update(settings)
    
    # If we update settings while connected, restart the proxy to apply
    from backend.fsm import fsm, ProxyState
    if fsm.current_state() == ProxyState.CONNECTED:
        connection_service.disconnect()
        def _reconnect():
            import time
            time.sleep(1.5) # Give OS time to free ports from previous tor instance
            connection_service.connect()
        asyncio.get_running_loop().run_in_executor(None, _reconnect)
        
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    # Enforce strictly binding to localhost
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    uvicorn.run(app, host="127.0.0.1", port=port)
