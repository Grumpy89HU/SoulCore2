import os
import time
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

def integrate_web_interface(app: FastAPI, core_instance):
    """
    Beoltja a fő FastAPI alkalmazást a SoulCore vizuális és API funkcióival.
    Ezzel elkerüljük a dupla szerver indítását és a port-konfliktust.
    """

    # --- Statikus fájlok kezelése ---
    # A /gui útvonal szolgálja ki a web mappát, a / pedig az index.html-t
    if os.path.exists("web"):
        app.mount("/gui", StaticFiles(directory="web"), name="gui")

    # --- Vizuális végpontok ---

    @app.get("/", response_class=HTMLResponse)
    async def root_web_access():
        """A Várkapu főoldala."""
        index_path = "web/index.html"
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return f.read()
        return """
        <body style='background:#0b0e14;color:#4a5568;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'>
            <div style='text-align:center;'>
                <h1 style='color:#3182ce;'>SOULCORE 2.0</h1>
                <p>A 'web/index.html' nem található a rendszerben.</p>
            </div>
        </body>
        """

    # --- API végpontok (Bővített) ---

    @app.post("/process")
    async def process_request(request: Request):
        """Standard pipeline feldolgozás."""
        try:
            data = await request.json()
            query = data.get("query") or data.get("message")
            
            if not query:
                raise HTTPException(status_code=400, detail="Üres bemenet.")

            # Hívás a Kernel-szintű Orchestratorra
            result = await core_instance.process_pipeline(query)
            return JSONResponse(content=result)
        
        except Exception as e:
            logging.error(f"WebGate Pipeline Hiba: {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.get("/telemetry")
    async def get_detailed_status():
        """Részletes rendszer-telemetria a GUI számára."""
        from main import gpu_telemetry  # A fő modul globális változója
        
        return {
            "identity": core_instance.config['project']['identity'],
            "uptime": int(time.time() - core_instance.start_time) if hasattr(core_instance, 'start_time') else "N/A",
            "hardware": gpu_telemetry,
            "slots": {name: slot.is_loaded for name, slot in core_instance.slots.items()},
            "vault": {
                "active": True if core_instance.db else False,
                "path": core_instance.config['database']['path']
            }
        }

    @app.get("/logs/stream")
    async def stream_logs():
        """(Opcionális) Itt később megvalósíthatunk egy élő naplófolyamot."""
        async def log_generator():
            yield "data: {\"msg\": \"Kapcsolat létrejött a log-szerverrel\"}\n\n"
        return StreamingResponse(log_generator(), media_type="text/event-stream")

    return app