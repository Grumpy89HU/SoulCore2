import uvicorn
import os, sys, signal, time, logging, asyncio, json, yaml
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.orchestrator import Orchestrator

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
    """A rendszer életciklusának kezelése (Startup & Shutdown)."""
    global core
    print("\n" + "="*60)
    print("    SOULCORE 2.0 - KERNEL AKTIVÁLÁSA")
    print("="*60)
    
    try:
        # 1. Orchestrator példányosítása
        core = Orchestrator()
        
        # 2. Modellek betöltése
        print("Slotok ébresztése...")
        core.boot_slots()
        
        # 3. Heartbeat elindítása
        heartbeat_task = asyncio.create_task(heartbeat_loop())
        
        print(f"\nSoulCore API online: http://{core.config['api']['host']}:{core.config['api']['port']}")
        
    except Exception as e:
        print(f"KRITIKUS HIBA AZ INDÍTÁSKOR: {e}")
        import traceback
        traceback.print_exc()

    yield

    # --- SHUTDOWN ---
    print("\n" + "="*60)
    print("    LEÁLLÍTÁSI SZEKVENCIA - VRAM FELSZABADÍTÁSA")
    print("="*60)
    
    if 'heartbeat_task' in locals():
        heartbeat_task.cancel()
    if core:
        core.shutdown()
    if HAS_GPU_MONITOR:
        pynvml.nvmlShutdown()
    
    print("A rendszerek biztonságosan leálltak. Viszlát, Grumpy!")

async def get_telemetry():
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
    global consecutive_errors, gpu_telemetry
    reflection_counter = 0
    REFLECTION_LIMIT = 30 

    while True:
        try:
            await asyncio.sleep(10)
            stats = await get_telemetry()
            
            if core:
                # Slot ellenőrzés
                for name, slot in core.slots.items():
                    if not slot.is_loaded:
                        logging.warning(f"Slot elakadás: {name}. Újraélesztés...")
                        slot.load()

                # Önreflexió
                reflection_counter += 1
                if reflection_counter >= REFLECTION_LIMIT:
                    temp_str = stats[0]['temp'] if stats else "N/A"
                    logging.info(f"Heartbeat: Hardver OK ({temp_str}). Önreflexió...")
                    await core.check_proactive_intent()
                    reflection_counter = 0

                consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors >= ERROR_THRESHOLD:
                os.execv(sys.executable, [sys.executable] + sys.argv)

# FastAPI definíció
app = FastAPI(title="SoulCore 2.0 Szuverén API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- ÚTVONALAK ---

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
    # Beolvassuk a konfigot a port és host miatt
    conf_path = "conf/soulcore_config.yaml"
    with open(conf_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    host = config['api'].get('host', '0.0.0.0')
    port = config['api'].get('port', 8000)
    
    uvicorn.run(app, host=host, port=port, reload=False)