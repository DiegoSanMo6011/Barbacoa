"""
AutoNoma POS Lite — Edge Server
FastAPI entry point
"""
import json
import logging
import time
import uuid

import jwt
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routers import productos, comandas, corte, auth, status as status_router, inventario, gastos, propinas
from core.config import settings, validate_runtime_security
from core.supabase_client import get_supabase

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("edge.request")


def _extract_claims_from_request(request: Request) -> dict[str, str | None]:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"tenant": None, "session_id": None}
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return {"tenant": None, "session_id": None}
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return {"tenant": None, "session_id": None}
    return {
        "tenant": str(payload.get("tenant")) if payload.get("tenant") else None,
        "session_id": str(payload.get("sid")) if payload.get("sid") else None,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_security()
    # Startup: verificar conexión a Supabase
    sb = get_supabase()
    try:
        # Verificamos conexión consultando comandas en lugar de tenants
        sb.table("comandas").select("id").limit(1).execute()
        print(f"✅ Supabase conectado — Tenant: {settings.TENANT_SLUG}")
    except Exception as e:
        print(f"⚠️  Sin conexión a Supabase: {e} — modo offline activado")
    yield

app = FastAPI(
    title="AutoNoma POS Lite — Edge API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started_at = time.perf_counter()
    claims = _extract_claims_from_request(request)
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(
            json.dumps(
                {
                    "request_id": request_id,
                    "tenant_id": claims["tenant"],
                    "session_id": claims["session_id"],
                    "method": request.method,
                    "endpoint": request.url.path,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                }
            )
        )
        raise

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "tenant_id": claims["tenant"],
                "session_id": claims["session_id"],
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            }
        )
    )
    return response

allow_origins = [origin.strip() for origin in settings.ALLOW_ORIGINS.split(",") if origin.strip()]
allow_origins.extend(["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "http://10.0.2.15:5173"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(productos.router, prefix="/productos",  tags=["Catálogo"])
app.include_router(comandas.router,  prefix="/comandas",   tags=["Ventas"])
app.include_router(corte.router,     prefix="/corte",      tags=["Corte de Caja"])
app.include_router(inventario.router, prefix="/inventario", tags=["Inventario"])
app.include_router(gastos.router,    prefix="/gastos",     tags=["Gastos"])
app.include_router(propinas.router,  prefix="/propinas",   tags=["Propinas"])
app.include_router(status_router.router, prefix="/status", tags=["Status"])
