import uvicorn
import os, sys, signal, time, logging, asyncio, json, yaml
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.orchestrator import Orchestrator
from src.utils.webserver import integrate_web_interface

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
gpu_telemetry = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    A rendszer életciklusának kezelése (Startup & Shutdown).
    Az Uvicorn indításakor ez a szekvencia fut le először.
    """
    global core
    print("\n" + "="*60)
    print("    SOULCORE 2.0 - KERNEL AKTIVÁLÁSA")
    print("="*60)
    
    try:
        # 1. Orchestrator példányosítása
        core = Orchestrator()
        
        # 2. Modellek (Slotok) betöltése
        print("Slotok ébresztése...")
        core.boot_slots()
        
        # 3. Heartbeat (GPU monitor és önreflexió) elindítása
        asyncio.create_task(heartbeat_loop())
        
        print(f"\n✅ SoulCore Kernel Online.")
        
    except Exception as e:
        print(f"❌ KRITIKUS HIBA AZ INDÍTÁSKOR: {e}")
        import traceback
        traceback.print_exc()

    yield

    # --- SHUTDOWN SZEKVENCIA ---
    print("\n" + "="*60)
    print("    LEÁLLÍTÁSI SZEKVENCIA - VRAM FELSZABADÍTÁSA")
    print("="*60)
    
    if core:
        core.shutdown()
    if HAS_GPU_MONITOR:
        pynvml.nvmlShutdown()
    
    print("A rendszerek biztonságosan leálltak. Viszlát, Grumpy!")

async def get_telemetry():
    """NVML alapú hardver adatok lekérése."""
    global gpu_telemetry
    if not HAS_GPU_MONITOR:
        return [{"id": 0, "temp": "N/A", "vram_used": "N/A", "load": "N/A"}]
    
    stats = []
    try:
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            stats.append({
                "id": i,
                "temp": f"{temp}°C",
                "vram_used": f"{mem.used // 1024**2} MB",
                "vram_total": f"{mem.total // 1024**2} MB",
                "load": f"{util.gpu}%"
            })
    except:
        return [{"error": "NVML hiba"}]
    
    gpu_telemetry = stats
    return stats

async def heartbeat_loop():
    """Folyamatos ellenőrzés és proaktív funkciók."""
    global consecutive_errors
    reflection_counter = 0
    REFLECTION_LIMIT = 30 

    while True:
        try:
            await asyncio.sleep(10)
            stats = await get_telemetry()
            
            if core:
                # Slotok életben tartása
                for name, slot in core.slots.items():
                    if not slot.is_loaded:
                        logging.warning(f"Slot elakadás: {name}. Újraélesztés...")
                        slot.load()

                # Önreflexiós ciklus
                reflection_counter += 1
                if reflection_counter >= REFLECTION_LIMIT:
                    temp_str = stats[0]['temp'] if stats else "N/A"
                    logging.info(f"Heartbeat: Hardver OK ({temp_str}). Önreflexió...")
                    await core.check_proactive_intent()
                    reflection_counter = 0

                consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            logging.error(f"Heartbeat hiba: {e}")
            if consecutive_errors >= ERROR_THRESHOLD:
                print("KRITIKUS HIBA - Rendszer újraindítása...")
                os.execv(sys.executable, [sys.executable] + sys.argv)

# --- FastAPI definíció ---
app = FastAPI(title="SoulCore 2.0 Szuverén API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- ALAP ÚTVONALAK ---

@app.get("/status")
async def status():
    return {
        "status": "online",
        "identity": core.config['project']['identity'] if core else "N/A",
        "hardware": gpu_telemetry,
        "active_slots": {name: slot.is_loaded for name, slot in core.slots.items()} if core else {},
        "timestamp": time.time()
    }

@app.post("/process")
async def process(request: Request):
    try:
        data = await request.json()
        user_query = data.get("query") or data.get("message")
        if not user_query:
            raise HTTPException(status_code=400, detail="Üres bemenet.")
        result = await core.process_pipeline(user_query)
        return JSONResponse(content=result)
    except Exception as e:
        logging.error(f"Feldolgozási hiba: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/stream")
async def stream(request: Request):
    async def event_generator():
        while True:
            if core and not core.outbound_queue.empty():
                msg = await core.outbound_queue.get()
                yield f"data: {json.dumps(msg)}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/system/restart")
async def restart_system():
    os.execv(sys.executable, [sys.executable] + sys.argv)

# --- INDÍTÁS ---

if __name__ == "__main__":
    # Konfiguráció beolvasása a hálózati adatokhoz
    conf_path = "conf/soulcore_config.yaml"
    with open(conf_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    host = config['api'].get('host', '0.0.0.0')
    port = config['api'].get('port', 8000)
    
    # 1. A Web Interface beintegrálása a modulból
    integrate_web_interface(app, core)

    # 2. Uvicorn indítása - ez aktiválja a lifespan-t és minden mást
    print(f"\n🏰 SoulCore 2.0 Várkapu nyitása: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=False, log_level="info")