import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BARBACOA_TIMEZONE = (os.getenv("BARBACOA_TIMEZONE") or "").strip()


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

# --- Autonoma dual-write (opcional) ---
AUTONOMA_SUPABASE_URL = (os.getenv("AUTONOMA_SUPABASE_URL") or "").strip() or None
AUTONOMA_SUPABASE_KEY = (os.getenv("AUTONOMA_SUPABASE_KEY") or "").strip() or None
AUTONOMA_TENANT_ID = (os.getenv("AUTONOMA_TENANT_ID") or "").strip() or None
AUTONOMA_PRODUCTO_OFFSET = int(os.getenv("AUTONOMA_PRODUCTO_OFFSET") or "0")
AUTONOMA_SUCURSAL_ID = (os.getenv("AUTONOMA_SUCURSAL_ID") or "").strip() or None
AUTONOMA_ENABLED = bool(
    AUTONOMA_SUPABASE_URL and AUTONOMA_SUPABASE_KEY and AUTONOMA_TENANT_ID
)
