import uvicorn
import os, sys, signal, time, logging, asyncio, json, yaml
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from src.orchestrator import Orchestrator
from src.utils.webserver import integrate_web_interface, set_core_reference

# --- Monitorozás inicializálása ---
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_GPU_MONITOR = True
except Exception:
    HAS_GPU_MONITOR = False

# Globális változók
core = None
consecutive_errors = 0
ERROR_THRESHOLD = 3
gpu_telemetry = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global core
    print("\n" + "="*60 + "\n    SOULCORE 2.0 - KERNEL AKTIVÁLÁSA\n" + "="*60)
    
    try:
        core = Orchestrator()
        print("Slotok ébresztése...")
        core.boot_slots()
        
        # Átadjuk a referenciát a webservernek, hogy elérje az SQL-t és a pipeline-t
        set_core_reference(core)
        
        # Háttérfolyamatok indítása
        heartbeat_task = asyncio.create_task(heartbeat_loop())
        
        print(f"\n✅ SoulCore Kernel Online.")
        yield
        heartbeat_task.cancel()
        
    except Exception as e:
        print(f"❌ KRITIKUS HIBA AZ INDÍTÁSKOR: {e}")
        import traceback
        traceback.print_exc()
        yield

    # --- SHUTDOWN SZEKVENCIA ---
    print("\n" + "="*60 + "\n    LEÁLLÍTÁSI SZEKVENCIA - VRAM FELSZABADÍTÁSA\n" + "="*60)
    if core: core.shutdown()
    if HAS_GPU_MONITOR:
        try: pynvml.nvmlShutdown()
        except: pass
    print("Rendszerek leállítva. Viszlát, Grumpy!")

async def update_gpu_stats():
    global gpu_telemetry
    if not HAS_GPU_MONITOR:
        gpu_telemetry = [{"id": 0, "temp": "N/A", "vram_used": 0, "load": 0}]
        return
    stats = []
    try:
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            stats.append({
                "id": i, "temp": temp, 
                "vram_used": mem.used // 1024**2, 
                "vram_total": mem.total // 1024**2, 
                "load": util.gpu
            })
        gpu_telemetry = stats
    except: pass

async def heartbeat_loop():
    global consecutive_errors
    reflection_counter = 0
    while True:
        try:
            await asyncio.sleep(5)
            await update_gpu_stats()
            if core:
                for name, slot in core.slots.items():
                    if hasattr(slot, 'enabled') and slot.enabled and not getattr(slot, 'is_loaded', False):
                        logging.warning(f"Slot elakadás: {name}. Újraélesztés...")
                        slot.load()
                
                reflection_counter += 1
                if reflection_counter >= 12:
                    if hasattr(core, 'check_proactive_intent'):
                        await core.check_proactive_intent()
                    reflection_counter = 0
            consecutive_errors = 0
        except asyncio.CancelledError: break
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors >= ERROR_THRESHOLD:
                os.execv(sys.executable, [sys.executable] + sys.argv)

# --- FastAPI ALKALMAZÁS ---
app = FastAPI(title="SoulCore 2.0 Szuverén API", lifespan=lifespan)

# MIDDLEWARE (MÉG INDÍTÁS ELŐTT!)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SessionMiddleware, secret_key="SOULCORE_SUPER_SECRET_KEY_2026")

# WEB INTERFACE INTEGRÁCIÓ (Routerek és Statikus fájlok)
integrate_web_interface(app)

# --- VÉGPONTOK ---

@app.get("/status")
async def status():
    # Itt adjuk át a friss GPU statisztikákat a fejlécnek
    return {
        "status": "online",
        "identity": core.identity if core else "N/A",
        "hardware": gpu_telemetry, # Ez frissül a heartbeat_loop-ban!
        "active_slots": {n: s.is_loaded for n, s in core.slots.items()} if core else {},
        "timestamp": time.time()
    }

@app.get("/telemetry")
async def get_full_telemetry(request: Request):
    if not core: raise HTTPException(status_code=503)
    try:
        return {
            "config": core.db.get_full_config(),
            "slots_info": {
                name: {
                    "enabled": getattr(slot, 'enabled', True),
                    "is_loaded": getattr(slot, 'is_loaded', False),
                    "filename": getattr(slot, 'filename', 'unknown'),
                    "max_vram_mb": getattr(slot, 'max_vram_mb', 0)
                } for name, slot in core.slots.items()
            },
            "hardware_status": gpu_telemetry
        }
    except Exception as e:
        logging.error(f"Telemetria hiba: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/settings/update_full")
async def update_settings(request: Request):
    if not core: raise HTTPException(status_code=503)
    try:
        data = await request.json()
        
        # 1. Alapkonfigurációk frissítése
        categories = ["project", "api", "hardware", "storage", "rag_system"]
        for cat in categories:
            if cat in data:
                core.db.set_config(cat, data[cat])
        
        # 2. Slotok frissítése
        if "slots" in data:
            for name, slot_data in data["slots"].items():
                core.db.save_slot(name, slot_data)
                # Ha a slot épp be van töltve, frissítjük az állapotát (opcionális)
                if name in core.slots:
                    core.slots[name].enabled = slot_data.get('enabled', 0)

        return {"status": "success", "message": "SoulCore konfiguráció frissítve."}
    except Exception as e:
        logging.error(f"Beállítás mentési hiba: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/process")
async def process(request: Request):
    if "user" not in request.session:
         return JSONResponse(status_code=401, content={"error": "Nincs hitelesítve"})
    try:
        data = await request.json()
        result = await core.process_pipeline(data.get("query"))
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/stream")
async def stream(request: Request):
    async def event_generator():
        while True:
            if core and hasattr(core, 'outbound_queue') and not core.outbound_queue.empty():
                msg = await core.outbound_queue.get()
                yield f"data: {json.dumps(msg)}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    # 1. Alapértelmezett értékek (Fallback)
    host = "0.0.0.0"
    port = 8000

    # 2. Megpróbáljuk kinyerni az SQL-ből az API konfigot, ha már létezik az adatbázis
    try:
        from src.database import SoulCoreDatabase
        db = SoulCoreDatabase()
        api_cfg = db.get_config("api")
        if api_cfg:
            host = api_cfg.get('host', host)
            port = int(api_cfg.get('port', port))
        db.close()
    except Exception as e:
        print(f"⚠️ Nem sikerült az SQL-ből tölteni a hálózati konfigot, alapértelmezett indítás: {e}")

    # 3. Indítás
    uvicorn.run(app, host=host, port=port)