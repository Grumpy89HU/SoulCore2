import uvicorn
import os, sys, signal, time, logging, asyncio, json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from src.orchestrator import Orchestrator
from src.utils.webserver import integrate_web_interface, set_core_reference
from src.utils.monitor import SoulCoreMonitor

# --- Globális Entitások ---
core: Orchestrator = None
monitor: SoulCoreMonitor = None
consecutive_errors = 0
ERROR_THRESHOLD = 3

@asynccontextmanager
async def lifespan(app: FastAPI):
    global core, monitor
    # Logging inicializálása, hogy lássuk a belső folyamatokat
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "═"*60 + "\n   SOULCORE 2.0 - KERNEL AKTIVÁLÁSA\n" + "═"*60)
    
    try:
        monitor = SoulCoreMonitor()
        core = Orchestrator()
        core.start_time = time.time()
        
        print("Slotok ébresztése és GGUF modellek előkészítése...")
        core.boot_slots()
        
        # --- VISSZAHOZOTT FEEDBACK CIKLUS ---
        for name, slot in core.slots.items():
            if getattr(slot, 'is_loaded', False):
                print(f"✅ Slot aktív: {name}")
            else:
                print(f"⚠️ Slot inaktív vagy hiba: {name}")
        # ------------------------------------
        
        set_core_reference(core)
        heartbeat_task = asyncio.create_task(heartbeat_loop())
        
        print(f"\n✅ SoulCore Kernel Online. Üdvözöllek, Grumpy.")
        yield
        
        heartbeat_task.cancel()
        print("\n" + "═"*60 + "\n   LEÁLLÍTÁSI SZEKVENCIA - VRAM ÜRÍTÉSE\n" + "═"*60)
        if core: core.shutdown()
        
    except Exception as e:
        print(f"❌ KRITIKUS KERNEL HIBA: {e}")
        import traceback
        traceback.print_exc()
        yield

async def heartbeat_loop():
    """Folyamatos ellenőrzés: Slotok állapota, VRAM biztonság és Proaktív gondolatok."""
    global consecutive_errors
    reflection_counter = 0
    
    while True:
        try:
            await asyncio.sleep(5) # 5 másodpercenkénti pulzus
            
            if core and monitor:
                # GPU állapot frissítése az Orchestrator számára
                current_stats = monitor.get_gpu_stats()
                core.last_hw_stats = current_stats 
                
                # Slot ellenőrzés: ha egy slot engedélyezve van, de nincs betöltve -> Újratöltés
                for name, slot in core.slots.items():
                    if getattr(slot, 'enabled', False) and not getattr(slot, 'is_loaded', False):
                        monitor.log_event("Kernel", f"Slot elakadás észlelve: {name}. Újraélesztés...", "warning")
                        slot.load()

                # VRAM Biztonsági fék
                if not monitor.check_vram_safety(threshold_pct=95.0):
                    monitor.log_event("Kernel", "VRAM Kritikus! Kényszerített cache ürítés...", "critical")
                    # Itt hívható egy core.flush_vram() ha szükséges

                # Proaktív ciklus (kb. percenként egyszer: 12 * 5s)
                reflection_counter += 1
                if reflection_counter >= 12:
                    if hasattr(core, 'check_proactive_intent'):
                        await core.check_proactive_intent()
                    reflection_counter = 0
            
            consecutive_errors = 0 # Sikeres ciklus után nullázunk
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            consecutive_errors += 1
            monitor.log_event("Heartbeat", f"Hiba: {e}", "error")
            if consecutive_errors >= ERROR_THRESHOLD:
                monitor.log_event("Kernel", "Összeomlás közeli állapot. Újraindítás...", "critical")
                os.execv(sys.executable, [sys.executable] + sys.argv)

# --- FastAPI ALKALMAZÁS KONFIGURÁCIÓ ---
app = FastAPI(title="SoulCore 2.0 Szuverén API", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SessionMiddleware, secret_key="SOULCORE_SUPER_SECRET_KEY_2026")

# Webfelület (index.html, login stb.) csatolása
integrate_web_interface(app)

# --- VÉGPONTOK (API réteg) ---

@app.get("/status")
async def status(request: Request):
    """Részletes állapotjelentés a GUI fejlécének."""
    if not core: return {"status": "starting"}
    
    return {
        "status": "online",
        "identity": core.identity,
        "hardware": core.last_hw_stats if hasattr(core, 'last_hw_stats') else [],
        "kernel": {
            "uptime": round(time.time() - core.start_time, 1),
            "slots_active": sum(1 for s in core.slots.values() if getattr(s, 'is_loaded', False))
        }
    }

@app.get("/telemetry")
async def get_full_telemetry(request: Request):
    """Minden beállítás és slot adat lekérése a beállítások panelhez."""
    if "user" not in request.session: raise HTTPException(status_code=403)
    if not core: raise HTTPException(status_code=503)
    
    return {
        "config": core.db.get_full_config(),
        "slots_info": {
            name: {
                "enabled": getattr(slot, 'enabled', True),
                "is_loaded": getattr(slot, 'is_loaded', False),
                "filename": getattr(slot, 'filename', 'unknown'),
                "max_vram_mb": getattr(slot, 'max_vram_mb', 0)
            } for name, slot in core.slots.items()
        }
    }

@app.post("/process")
async def process_api(request: Request):
    """Fő feldolgozó végpont (GUI-ból hívva)."""
    if "user" not in request.session:
        return JSONResponse(status_code=401, content={"error": "Nincs hitelesítve"})
    
    try:
        data = await request.json()
        # Orchestrator hívása: query, chat_id és a session-ből jövő user
        result = await core.process_pipeline(
            user_query=data.get("query"),
            chat_id=data.get("chat_id", "default_chat"),
            user_id=request.session.get("user")
        )
        return JSONResponse(content=result)
    except Exception as e:
        monitor.log_event("API", f"Feldolgozási hiba: {e}", "error")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/stream")
async def stream_output(request: Request):
    """Eseményalapú válaszfolyam (SSE) a válaszok szavankénti megjelenítéséhez."""
    async def event_generator():
        while True:
            if core and hasattr(core, 'outbound_queue'):
                if not core.outbound_queue.empty():
                    msg = await core.outbound_queue.get()
                    yield f"data: {json.dumps(msg)}\n\n"
            await asyncio.sleep(0.1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    host, port = "0.0.0.0", 8000
    
    # Hálózati konfig betöltése az adatbázisból (ha már létezik)
    try:
        from src.database import SoulCoreDatabase
        db = SoulCoreDatabase()
        api_cfg = db.get_config("api")
        if api_cfg:
            host = api_cfg.get('host', host)
            port = int(api_cfg.get('port', port))
        db.close()
    except:
        pass

    uvicorn.run(app, host=host, port=port, log_level="info")