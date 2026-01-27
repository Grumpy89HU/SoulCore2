import uvicorn
import os, sys, signal, time, traceback, json, asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# SoulCore 2.0 Belső modulok
from src.orchestrator import Orchestrator

# Globális Orchestrator példány
core = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """A rendszer életciklusának kezelése (Startup & Shutdown)."""
    global core
    print("\n" + "="*60)
    print("   SOULCORE 2.0 - KERNEL AKTIVÁLÁSA")
    print("="*60)
    
    try:
        # 1. Orchestrator példányosítása (Konfiguráció betöltése)
        core = Orchestrator()
        
        # 2. Modellek betöltése a VRAM-ba
        print("Slotok ébresztése...")
        core.boot_slots()
        
        print(f"\nSoulCore API online: http://{core.config['api']['host']}:{core.config['api']['port']}")
        
    except Exception as e:
        print(f"KRITIKUS HIBA AZ INDÍTÁSKOR: {e}")
        traceback.print_exc()

    yield  # Itt fut az alkalmazás

    # --- SHUTDOWN (VRAM ÜRÍTÉSE) ---
    print("\n" + "="*60)
    print("   LEÁLLÍTÁSI SZEKVENCIA - VRAM FELSZABADÍTÁSA")
    print("="*60)
    if core:
        core.shutdown()
    print("A rendszerek biztonságosan leálltak. Viszlát, Grumpy!")

# FastAPI app definíció
app = FastAPI(title="SoulCore 2.0 API", lifespan=lifespan)

# --- DINAMIKUS CORS BEÁLLÍTÁS ---
# Ideiglenesen létrehozunk egy alap Orchestratort a config olvasásához a middleware-hez
temp_cfg = Orchestrator() if core is None else core
app.add_middleware(
    CORSMiddleware,
    allow_origins=temp_cfg.config['api'].get('cors_origins', ["*"]),
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- API ÚTVONALAK (OpenAI Kompatibilitás) ---

@app.get("/")
async def status():
    return {
        "status": "online",
        "identity": core.config['project']['identity'],
        "slots": {name: "active" for name in core.slots}
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
        user_query = next((msg["content"] for msg in reversed(messages) if msg["role"] == "user"), "")
        
        # Lefuttatjuk a teljes SoulCore Pipeline-t
        # Scribe -> Valet -> Sovereign
        result = core.process_pipeline(user_query)
        
        # Válasz összeállítása OpenAI formátumban
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "soulcore-2.0",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result.get('response', '')},
                "finish_reason": "stop"
            }]
        }
    except Exception as e:
        core.logger.error(f"API HIBA: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- RENDSZER VEZÉRLÉS ---

@app.post("/system/restart")
async def restart_system():
    """Tiszta újraindítás: VRAM ürítés és folyamat újratöltése."""
    print("Kézi újraindítás kezdeményezve...")
    # Az os.execv miatt a lifespan shutdown lefut, kiürítve a GPU-t
    os.execv(sys.executable, [sys.executable] + sys.argv)

@app.post("/system/stop")
async def stop_system():
    """A rendszer teljes leállítása."""
    print("Leállítás kezdeményezve...")
    os.kill(os.getpid(), signal.SIGINT)
    return {"status": "stopping"}

if __name__ == "__main__":
    # Indítás a configban megadott adatokkal
    host = temp_cfg.config['api'].get('host', '0.0.0.0')
    port = temp_cfg.config['api'].get('port', 8000)
    
    uvicorn.run(app, host=host, port=port)