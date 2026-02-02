from passlib.context import CryptContext
import sqlite3
import json

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_admin():
    db_path = "vault/db/soulcore.db"
    # A jelszó: soulcore
    hashed = pwd_context.hash("soulcore")
    
    conn = sqlite3.connect(db_path)
    # Létrehozzuk az auth táblát, ha még nincs
    conn.execute('CREATE TABLE IF NOT EXISTS auth (username TEXT PRIMARY KEY, password_hash TEXT)')
    # Beillesztjük az admint
    conn.execute('INSERT OR REPLACE INTO auth VALUES (?, ?)', ("admin", hashed))
    conn.commit()
    conn.close()
    print("✅ Admin hitelesítési adatok rögzítve a széfben.")

if __name__ == "__main__":
    init_admin()
