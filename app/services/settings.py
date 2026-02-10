import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except Exception:
        return default
    return max(1.0, value)


SUPABASE_TIMEOUT_SECONDS = _env_float("BARBACOA_SUPABASE_TIMEOUT_SECONDS", 20.0)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Falta SUPABASE_URL o SUPABASE_KEY en el archivo .env")
