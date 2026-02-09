import uvicorn
import os, sys, signal, time, logging, asyncio, json, psutil
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

# --- Intelligens Forgalomszabályozó ---
class TrafficController:
    def __init__(self):
        self.request_count = 0
        self.start_time = time.time()
        self.last_query = ""

    def is_spammy(self, current_query: str) -> bool:
        """Kiszűri a véletlen dupla küldéseket."""
        if current_query and current_query == self.last_query:
            return True
        self.last_query = current_query
        return False

traffic = TrafficController()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global core, monitor
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "═"*60 + "\n    SOULCORE 2.1 - SZUVERÉN KERNEL AKTIVÁLÁSA\n" + "═"*60)
    
    try:
        monitor = SoulCoreMonitor()
        core = Orchestrator()
        core.start_time = time.time()
        
        print("Slotok ébresztése és GGUF modellek előkészítése...")
        core.boot_slots()
        
        # --- FEEDBACK CIKLUS ---
        for name, slot in core.slots.items():
            status = "✅ Aktív" if getattr(slot, 'is_loaded', False) else "⚠️ Inaktív/Hiba"
            print(f"[{name.upper()}] status: {status}")
        
        set_core_reference(core)
        heartbeat_task = asyncio.create_task(heartbeat_loop())
        
        print(f"\n✅ SoulCore Kernel Online. Üdvözöllek, Grumpy.")
        yield
        
        heartbeat_task.cancel()
        print("\n" + "═"*60 + "\n    LEÁLLÍTÁSI SZEKVENCIA - VRAM ÜRÍTÉSE\n" + "═"*60)
        if core: core.shutdown()
        
    except Exception as e:
        print(f"❌ KRITIKUS KERNEL HIBA: {e}")
        import traceback
        traceback.print_exc()
        yield

async def heartbeat_loop():
    """Folyamatos ellenőrzés: Slotok, VRAM és Önvizsgálat."""
    global consecutive_errors
    reflection_counter = 0
    
    while True:
        try:
            await asyncio.sleep(5)
            
            if core and monitor:
                # JAVÍTVA: Az új hardver-lekérdező metódus használata
                current_stats = monitor.get_hardware_stats()
                core.last_hw_stats = current_stats 
                
                # Slot figyelő
                for name, slot in core.slots.items():
                    if getattr(slot, 'enabled', False) and not getattr(slot, 'is_loaded', False):
                        monitor.log_event("Kernel", f"Slot elakadás: {name}. Újraélesztés...", "warning")
                        try: slot.load()
                        except: pass

                # VRAM Védelem
                if not monitor.check_vram_safety(threshold_pct=95.0):
                    monitor.log_event("Kernel", "VRAM KRITIKUS! Puffer ürítése javasolt.", "critical")

                # Kognitív ciklus (percenként)
                reflection_counter += 1
                if reflection_counter >= 12:
                    if hasattr(core, 'check_proactive_intent'):
                        await core.check_proactive_intent()
                    reflection_counter = 0
            
            consecutive_errors = 0 
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            consecutive_errors += 1
            if monitor: monitor.log_event("Heartbeat", f"Hiba: {e}", "error")
            if consecutive_errors >= ERROR_THRESHOLD:
                if monitor: monitor.log_event("Kernel", "Kritikus hiba. Újraindítás...", "critical")
                os.execv(sys.executable, [sys.executable] + sys.argv)

# --- FastAPI APP ---
app = FastAPI(title="SoulCore 2.1 Szuverén API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SessionMiddleware, secret_key="SOULCORE_SUPER_SECRET_KEY_2026")

integrate_web_interface(app)

# --- VÉGPONTOK ---

@app.get("/status")
async def status(request: Request):
    if not core: return {"status": "starting"}
    return {
        "status": "online",
        "identity": core.identity,
        "hardware": core.last_hw_stats if hasattr(core, 'last_hw_stats') else [],
        "kernel": {
            "uptime": round(time.time() - core.start_time, 1),
            "slots_active": sum(1 for s in core.slots.values() if getattr(s, 'is_loaded', False)),
            "requests_processed": traffic.request_count
        }
    }

@app.get("/kernel/health")
async def kernel_health(request: Request):
    """Részletes belső diagnosztika."""
    if "user" not in request.session: raise HTTPException(status_code=401)
    process = psutil.Process(os.getpid())
    return {
        "memory_rss_mb": process.memory_info().rss // 1024**2,
        "cpu_threads": process.num_threads(),
        "uptime_sec": round(time.time() - (core.start_time if core else time.time()), 1),
        "requests_total": traffic.request_count
    }

@app.post("/kernel/panic")
async def system_panic(request: Request):
    """Vészhelyzeti VRAM ürítés."""
    if "user" not in request.session: raise HTTPException(status_code=403)
    monitor.log_event("Kernel", "!!! PANIC MODE - SLOTOK ÜRÍTÉSE !!!", "critical")
    for name, slot in core.slots.items():
        if hasattr(slot, 'unload'): slot.unload()
    return {"status": "flushed", "message": "VRAM felszabadítva."}

@app.post("/process")
async def process_api(request: Request):
    if "user" not in request.session:
        return JSONResponse(status_code=401, content={"error": "Nincs hitelesítve"})
    
    try:
        data = await request.json()
        query = data.get("query", "")

        if traffic.is_spammy(query):
            return JSONResponse(content={"answer": "Ismételt kérés észlelve, kérlek várj...", "type": "warning"})

        traffic.request_count += 1
        result = await core.process_pipeline(
            user_query=query,
            chat_id=data.get("chat_id", "default_chat"),
            user_id=request.session.get("user")
        )
        return JSONResponse(content=result)
    except Exception as e:
        if monitor: monitor.log_event("API", f"Hiba: {e}", "error")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/stream")
async def stream_output(request: Request):
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
    try:
        from src.database import SoulCoreDatabase
        db = SoulCoreDatabase()
        api_cfg = db.get_config("api")
        if api_cfg:
            host = api_cfg.get('host', host)
            port = int(api_cfg.get('port', port))
        db.close()
    except: pass
    uvicorn.run(app, host=host, port=port, log_level="info")