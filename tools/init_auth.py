import sqlite3
import os
import sys

# Hozzáadjuk a jelenlegi könyvtárat az útvonalhoz, hogy elérjük a database.py-t
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import SoulCoreDatabase

def init_system_access():
    """
    Létrehozza a kezdeti hozzáféréseket a SoulCore rendszerhez.
    Ez a fájl csak egyszer, az inicializáláskor fut le.
    """
    print("🗝️ SoulCore 2.0 Hozzáférés-kezelő inicializálása...")
    
    db = SoulCoreDatabase()
    
    # 1. Admin (Rendszergazda) létrehozása
    # Alapértelmezett jelszó: soulcore
    admin_user = "admin"
    admin_pass = "soulcore"
    
    print(f"👤 Rendszergazda ({admin_user}) generálása...")
    db.create_user(admin_user, admin_pass, role="sovereign")
    
    # 2. Grumpy (A Mester) létrehozása
    # Alapértelmezett jelszó: soulcore_admin
    master_user = "Grumpy"
    master_pass = "soulcore_admin"
    
    print(f"🛠️ Mester hozzáférés ({master_user}) generálása...")
    db.create_user(master_user, master_pass, role="admin")

    # 3. Ellenőrzés
    with sqlite3.connect(db.db_path) as conn:
        auth_count = conn.execute("SELECT COUNT(*) FROM auth").fetchone()[0]
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        
    print("---")
    print(f"✅ Hitelesítési tábla: {auth_count} bejegyzés.")
    print(f"✅ Felhasználói tábla: {user_count} bejegyzés.")
    print("🚀 SoulCore hozzáférés élesítve. Használhatod a webes felületet.")
    
    db.close()

if __name__ == "__main__":
    # Biztonsági ellenőrzés: létezik-e a mappa
    os.makedirs("vault/db", exist_ok=True)
    init_system_access()