import uvicorn
import os, sys, signal, time, logging, asyncio, json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.orchestrator import Orchestrator

# Globális Orchestrator és állapot kezelés
core = None
consecutive_errors = 0
ERROR_THRESHOLD = 3

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
        
        # 2. Modellek betöltése a VRAM-ba
        print("Slotok ébresztése...")
        core.boot_slots()
        
        # 3. Heartbeat (Szívverés) elindítása háttérfolyamatként
        heartbeat_task = asyncio.create_task(heartbeat_loop())
        
        print(f"\nSoulCore API online: http://{core.config['api']['host']}:{core.config['api']['port']}")
        
    except Exception as e:
        print(f"KRITIKUS HIBA AZ INDÍTÁSKOR: {e}")
        import traceback
        traceback.print_exc()

    yield  # Itt fut a szerver

    # --- SHUTDOWN (VRAM ÜRÍTÉSE) ---
    print("\n" + "="*60)
    print("    LEÁLLÍTÁSI SZEKVENCIA - VRAM FELSZABADÍTÁSA")
    print("="*60)
    
    heartbeat_task.cancel()
    if core:
        core.shutdown()
    
    print("A rendszerek biztonságosan leálltak. Viszlát, Grumpy!")

async def heartbeat_loop():
    """
    Kognitív órajel és Öngyógyító Sentry.
    Feladata: Proaktív üzenetek, állapotfigyelés és szükség esetén újraindítás.
    """
    global consecutive_errors
    reflection_counter = 0
    # ~5 perc (30 ciklus * 10mp)
    REFLECTION_LIMIT = 30 

    while True:
        try:
            # 1. Alapütem: 10 másodperces ellenőrzés
            await asyncio.sleep(10)
            
            if core:
                # 2. Rendszer-egészség ellenőrzése (Slot figyelés)
                for name, slot in core.slots.items():
                    if not slot.is_loaded:
                        logging.warning(f"Slot elakadás: {name}. Újraélesztés...")
                        slot.load()

                # 3. Önreflexió és proaktív üzenetek (Kópé magától szól)
                reflection_counter += 1
                if reflection_counter >= REFLECTION_LIMIT:
                    logging.info("Heartbeat: Önreflexiós ciklus indítása...")
                    await core.check_proactive_intent()
                    reflection_counter = 0

                # Siker esetén nullázzuk a hiba számlálót
                consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            logging.error(f"Heartbeat hiba ({consecutive_errors}/{ERROR_THRESHOLD}): {e}")
            
            if consecutive_errors >= ERROR_THRESHOLD:
                print("!!! KRITIKUS HIBA: ÖNGYÓGYÍTÓ ÚJRAINDÍTÁS INDUL !!!")
                # Értesítjük a klienst a streamen, mielőtt meghalunk
                if core:
                    await core.outbound_queue.put({
                        "type": "system_event",
                        "response": "Rendszerhiba észlelve. Újraindítom magam...",
                        "timestamp": time.time()
                    })
                await asyncio.sleep(2)
                os.execv(sys.executable, [sys.executable] + sys.argv)

# FastAPI app definíció
app = FastAPI(title="SoulCore 2.0 Szuverén API", lifespan=lifespan)

# --- DINAMIKUS CORS BEÁLLÍTÁS ---
def get_current_cfg():
    return Orchestrator().config if core is None else core.config

temp_cfg = get_current_cfg()
app.add_middleware(
    CORSMiddleware,
    allow_origins=temp_cfg['api'].get('cors_origins', ["*"]),
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- SZUVERÉN API ÚTVONALAK ---

@app.get("/status")
async def status():
    return {
        "status": "online",
        "identity": core.config['project']['identity'],
        "active_slots": {name: slot.is_loaded for name, slot in core.slots.items()},
        "vram_limit": core.config['hardware'].get('total_vram_limit_mb', "N/A")
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

# --- RENDSZER VEZÉRLÉS ---

@app.post("/system/restart")
async def restart_system():
    print("Kézi újraindítás kezdeményezve...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

@app.post("/system/stop")
async def stop_system():
    print("Leállítás kezdeményezve...")
    os.kill(os.getpid(), signal.SIGINT)
    return {"status": "stopping"}

if __name__ == "__main__":
    host = temp_cfg['api'].get('host', '0.0.0.0')
    port = temp_cfg['api'].get('port', 8000)
    uvicorn.run(app, host=host, port=port)