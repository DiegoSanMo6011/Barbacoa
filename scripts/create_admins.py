import os
import bcrypt
from supabase import create_client
from dotenv import load_dotenv


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Falta SUPABASE_URL o SUPABASE_KEY")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

usuarios = [
    {"nombre": "Admin Negocio 1", "usuario": "ADMIN1"},
    {"nombre": "Admin Negocio 2", "usuario": "ADMIN2"},
    {"nombre": "Admin Negocio 3", "usuario": "ADMIN3"},
    {"nombre": "AutoNoma", "usuario": "AUTONOMA"},
]

password = "TEST1"
password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

for u in usuarios:
    data = {
        "nombre": u["nombre"],
        "usuario": u["usuario"],
        "password_hash": password_hash,
        "rol": "ADMIN",
        "activo": True,
    }
    res = client.table("usuarios").insert(data).execute()
    print(res.data)
