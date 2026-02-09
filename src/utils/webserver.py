import os
import logging
import psutil
import time
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from typing import Optional

logger = logging.getLogger("soulcore.web")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_internal_core = None 

def integrate_web_interface(app: FastAPI):
    """Regisztrálja a webes felület útvonalait és a kognitív motor összeköttetéseit."""
    
    # Statikus fájlok kiszolgálása
    if os.path.exists("web"):
        app.mount("/gui_static", StaticFiles(directory="web"), name="gui_static")

    def check_core():
        if _internal_core is None:
            raise HTTPException(status_code=503, detail="SoulCore Kernel Offline")
        return _internal_core

    # --- AUTHENTICATION ---
    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        path = "web/login.html"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: return f.read()
        return "<h4>SoulCore Login Required</h4><form method='POST'><input name='username'><input type='password' name='password'><button>Enter</button></form>"

    @app.post("/login")
    async def login(request: Request):
        try:
            data = await request.json()
            username = data.get("username")
            password = data.get("password")
            
            # DB alapú ellenőrzés prioritása
            if _internal_core and hasattr(_internal_core.db, 'verify_user'):
                if _internal_core.db.verify_user(username, password):
                    request.session["user"] = username
                    return {"status": "success"}

            # Szuverén Fallback
            if username == "admin" and password == "soulcore":
                request.session["user"] = "Grumpy"
                return {"status": "success"}
        except: pass
        raise HTTPException(status_code=401, detail="Hozzáférés megtagadva")

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login")

    # --- API & CONTROL ---
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        if "user" not in request.session: return RedirectResponse(url="/login")
        path = "web/index.html"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: return f.read()
        return "Main GUI missing in /web folder."

    @app.get("/chats/list")
    async def list_chats(request: Request):
        if "user" not in request.session: return []
        core = check_core()
        return core.db.get_all_chat_sessions() if hasattr(core.db, 'get_all_chat_sessions') else []

    @app.get("/chats/history/{chat_id}")
    async def get_history(chat_id: str, request: Request):
        if "user" not in request.session: return []
        core = check_core()
        return core.db.get_chat_history(chat_id)

    @app.post("/process")
    async def process(request: Request):
        if "user" not in request.session: raise HTTPException(status_code=403)
        core = check_core()
        data = await request.json()
        
        # Pipeline indítása
        result = await core.process_pipeline(
            user_query=data.get("query"),
            chat_id=data.get("chat_id", "default"),
            user_id=request.session.get("user")
        )
        return JSONResponse(content=result)

    @app.get("/status")
    async def get_status(request: Request):
        if "user" not in request.session: return {}
        core = check_core()
        
        # Monitor adatok lehívása
        hw_stats = core.get_hardware_stats() if hasattr(core, 'get_hardware_stats') else {}
        
        return {
            "hardware": hw_stats,
            "kernel": {
                "uptime": round(time.time() - core.start_time, 1),
                "active_slots": len(core.slots)
            },
            "system": {
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent
            }
        }

    @app.get("/telemetry")
    async def get_telemetry(request: Request):
        if "user" not in request.session: return {}
        core = check_core()
        return {
            "config": core.config if hasattr(core, 'config') else {},
            "slots_info": core.get_slots_status() if hasattr(core, 'get_slots_status') else {}
        }

    @app.post("/settings/update_full")
    async def update_settings(request: Request):
        if "user" not in request.session: return {"status": "denied"}
        core = check_core()
        data = await request.json()
        if hasattr(core, 'update_system_config'):
            core.update_system_config(data)
            return {"status": "ok"}
        return {"status": "not_implemented"}

    return app

def set_core_reference(instance):
    global _internal_core
    _internal_core = instance