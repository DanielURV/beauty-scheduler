import sqlite3

con = sqlite3.connect("beauty_scheduler.db")
cur = con.cursor()

# --- clients: nuevas columnas ---
existing = [row[1] for row in cur.execute("PRAGMA table_info(clients)")]
for col, definition in [
    ("email",      "TEXT"),
    ("notes",      "TEXT"),
    ("is_blocked", "INTEGER DEFAULT 0"),
]:
    if col not in existing:
        cur.execute(f"ALTER TABLE clients ADD COLUMN {col} {definition}")
        print(f"+ clients.{col}")
    else:
        print(f"  clients.{col} ya existe")

# --- crear tablas nuevas via SQLAlchemy (business_hours, admin_users) ---
import sys
sys.path.insert(0, ".")
from src.models.database import Base, engine
Base.metadata.create_all(bind=engine)
print("+ tablas business_hours y admin_users creadas (si no existian)")

con.commit()
con.close()
print("Migracion completada.")
