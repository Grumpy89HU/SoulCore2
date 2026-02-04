import os
import logging
import psutil  # Új függőség a telemetriához
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext

# Naplózás beállítása
logger = logging.getLogger("soulcore.web")

# Biztonsági konfiguráció
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_internal_core = None  # Globális referencia az Orchestratorhoz

def integrate_web_interface(app: FastAPI):
    """Regisztrálja a webes felület útvonalait és a logikát."""
    
    # Statikus fájlok kiszolgálása a GUI-hoz
    if os.path.exists("web"):
        app.mount("/gui", StaticFiles(directory="web"), name="gui")
        # Biztosítjuk, hogy a statikus assetek is elérhetőek legyenek
        app.mount("/gui_static", StaticFiles(directory="web"), name="gui_static")

    # --- Segédfüggvény a Core ellenőrzéséhez ---
    def check_core():
        if _internal_core is None:
            raise HTTPException(status_code=503, detail="SoulCore Kernel nem elérhető.")
        return _internal_core

    # --- Auth Végpontok ---
    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        login_path = "web/login.html"
        if os.path.exists(login_path):
            with open(login_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Login page missing. Please check 'web/login.html' path."

    @app.post("/login")
    async def login(request: Request):
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        # 1. Próbálkozás az adatbázis alapú azonosítással
        if _internal_core and hasattr(_internal_core.db, 'verify_user'):
            if _internal_core.db.verify_user(username, password):
                request.session["user"] = username
                return {"status": "success"}

        # 2. Hardcoded fallback (Amnézia-gyilkos alapértelmezett)
        if username == "admin" and password == "soulcore":
            request.session["user"] = username
            return {"status": "success"}
        
        raise HTTPException(status_code=401, detail="Helytelen adatok")

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login")

    # --- Védett Végpontok (UI & API) ---
    
    @app.get("/", response_class=HTMLResponse)
    async def root_web_access(request: Request):
        if "user" not in request.session:
            return RedirectResponse(url="/login")
        index_path = "web/index.html"
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Index page missing. Check 'web/index.html'."

    @app.get("/chats/list")
    async def list_chats(request: Request):
        if "user" not in request.session: raise HTTPException(status_code=403)
        core = check_core()
        try:
            # Ha nincs még ilyen metódus, adjunk vissza üres listát hiba helyett
            if hasattr(core.db, 'get_all_chat_sessions'):
                chats = core.db.get_all_chat_sessions() 
            else:
                logger.warning("Database missing 'get_all_chat_sessions' method.")
                chats = []
            return JSONResponse(content=chats)
        except Exception as e:
            logger.error(f"Error listing chats: {e}")
            return JSONResponse(content=[])

    @app.get("/chats/history/{chat_id}")
    async def get_chat_history(chat_id: str, request: Request):
        if "user" not in request.session: raise HTTPException(status_code=403)
        core = check_core()
        history = core.db.get_chat_history(chat_id)
        return JSONResponse(content=history)

    @app.post("/process")
    async def process_request(request: Request):
        if "user" not in request.session: raise HTTPException(status_code=403)
        core = check_core()
        data = await request.json()
        
        # Kinyerjük a session-ben lévő júzert (pl. admin vagy Grumpy)
        current_user = request.session.get("user")
        
        # Orchestrator hívás - most már minden paraméterrel
        result = await core.process_pipeline(
            user_query=data.get("query"), 
            chat_id=data.get("chat_id", "default_chat"),
            user_id=current_user  # Átadjuk a session-ből a júzert!
        )
        return JSONResponse(content=result)

    @app.get("/status")
    async def get_system_status(request: Request):
        """Hardware és Kernel telemetria."""
        if "user" not in request.session: raise HTTPException(status_code=403)
        core = check_core()
        
        # Dinamikus fallback, ha az Orchestratorban nincs implementálva
        if hasattr(core, 'get_hardware_stats'):
            stats = core.get_hardware_stats()
        else:
            stats = {
                "cpu_usage": psutil.cpu_percent(),
                "ram_usage": psutil.virtual_memory().percent,
                "status": "online (limited telemetry)"
            }
        return JSONResponse(content=stats)

    @app.get("/telemetry")
    async def get_full_config(request: Request):
        if "user" not in request.session: raise HTTPException(status_code=403)
        core = check_core()
        config_data = {
            "config": getattr(core, 'config', {}),
            "slots_info": core.get_slots_status() if hasattr(core, 'get_slots_status') else "N/A"
        }
        return JSONResponse(content=config_data)

    @app.post("/settings/update_full")
    async def update_full_settings(request: Request):
        if "user" not in request.session: raise HTTPException(status_code=403)
        core = check_core()
        data = await request.json()
        if hasattr(core, 'update_system_config'):
            core.update_system_config(data)
            return {"status": "ok"}
        raise HTTPException(status_code=501, detail="Update method not implemented")

    return app

def set_core_reference(instance):
    global _internal_core
    _internal_core = instance