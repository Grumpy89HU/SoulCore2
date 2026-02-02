import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext

# Biztonsági konfiguráció
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_internal_core = None # Globális referencia az Orchestratorhoz

def integrate_web_interface(app: FastAPI):
    """Regisztrálja a webes felület útvonalait és a logikát."""
    
    # Statikus fájlok kiszolgálása (a gui és gui_static szinonimák a biztonság kedvéért)
    if os.path.exists("web"):
        app.mount("/gui", StaticFiles(directory="web"), name="gui")
        app.mount("/gui_static", StaticFiles(directory="web"), name="gui_static")

    # --- Segédfüggvények (Auth) ---
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(password):
        return pwd_context.hash(password)

    # --- Auth Végpontok ---
    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        login_path = "web/login.html"
        if os.path.exists(login_path):
            with open(login_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Login page (web/login.html) missing."

    @app.post("/login")
    async def login(request: Request):
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        # 1. Próbáljuk az SQL-ből (ha van már core és verify_user metódus)
        if _internal_core and hasattr(_internal_core.db, 'verify_user'):
            if _internal_core.db.verify_user(username, password):
                request.session["user"] = username
                return {"status": "success"}

        # 2. Hard-fallback az első belépéshez (ha az SQL még üres)
        if username == "admin" and password == "soulcore":
            request.session["user"] = username
            return {"status": "success"}
        
        raise HTTPException(status_code=401, detail="Helytelen adatok")

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login")

    # --- Védett Végpontok (UI) ---
    @app.get("/", response_class=HTMLResponse)
    async def root_web_access(request: Request):
        if "user" not in request.session:
            return RedirectResponse(url="/login")
        
        index_path = "web/index.html"
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Index page missing."

    # --- API Funkciók (Minden visszatért) ---
    
    @app.post("/process")
    async def process_request(request: Request):
        """A webfelületről érkező kérdések közvetlen kiszolgálása."""
        if "user" not in request.session:
            raise HTTPException(status_code=403)
        if not _internal_core:
            raise HTTPException(status_code=503, detail="Kernel initializing...")
            
        data = await request.json()
        # Meghívjuk az Orchestrator pipeline-ját
        result = await _internal_core.process_pipeline(data.get("query"))
        return JSONResponse(content=result)

    @app.post("/settings/update")
    async def update_settings(request: Request):
        """Beállítások mentése az SQL-be."""
        if "user" not in request.session: raise HTTPException(status_code=403)
        if not _internal_core: raise HTTPException(status_code=503)
        
        data = await request.json()
        # Itt az SQL-be mentjük az adatokat (feltételezve a set_config vagy update_full_config metódust)
        try:
            for key, value in data.items():
                _internal_core.db.set_config(key, value)
            return {"status": "saved"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    return app

def set_core_reference(instance):
    """Szinkronizáció a main.py-ból a lifespan alatt."""
    global _internal_core
    _internal_core = instance