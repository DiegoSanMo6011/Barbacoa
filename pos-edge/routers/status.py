"""
Router: Status del Edge Server
"""
from fastapi import APIRouter
from models.schemas import StatusOut
from core.supabase_client import get_supabase
from core.config import settings
import datetime

router = APIRouter()

@router.get("", response_model=StatusOut)
async def get_status(): # Changed to async def
    online = False
    try:
        sb = await get_supabase_client() # Changed to await get_supabase_client()
        sb.table("comandas").select("id").limit(1).execute() # Changed table name to "comandas"
        online = True
    except Exception:
        pass

    return StatusOut(
        status="ok",
        version="1.0.0",
        tenant_id=settings.TENANT_ID,
        tenant_slug=settings.TENANT_SLUG,
        supabase_online=online,
        timestamp=datetime.datetime.utcnow(),
    )
