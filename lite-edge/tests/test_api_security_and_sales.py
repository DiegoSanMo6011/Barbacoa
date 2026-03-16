from __future__ import annotations

from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from core.config import settings
from core.security import get_current_user, require_roles
from core.session_registry import clear_all_sessions_for_tests
from models.schemas import UnlockRequest, VentaCreate
from routers import auth as auth_router
from routers import comandas as comandas_router


class FakeSupabase:
    def __init__(self, *, no_jornada: bool = False):
        self.no_jornada = no_jornada
        self.sales: dict[str, dict] = {}
        self._folio = 100

    def rpc(self, name: str, params: dict):
        if name != "crear_venta_lite":
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=[]))

        def _execute():
            if self.no_jornada:
                raise Exception("No hay jornada ABIERTA para registrar venta")

            sale_id = params["p_client_sale_id"]
            if sale_id in self.sales:
                return SimpleNamespace(data={**self.sales[sale_id], "deduplicated": True})

            self._folio += 1
            data = {
                "comanda_id": str(uuid.uuid4()),
                "folio": self._folio,
                "total": params["p_total"],
                "cambio": 0,
                "deduplicated": False,
            }
            self.sales[sale_id] = data
            return SimpleNamespace(data=data)

        return SimpleNamespace(execute=_execute)


def _dummy_request(path: str):
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        state=SimpleNamespace(request_id="req-test"),
        url=SimpleNamespace(path=path),
    )


class ApiSecurityAndSalesTests(unittest.TestCase):
    def setUp(self) -> None:
        auth_router._FAILED_ATTEMPTS.clear()
        auth_router._LOCKED_UNTIL.clear()
        clear_all_sessions_for_tests()
        self.user_ctx = {
            "tenant": settings.TENANT_ID,
            "rol": "CAJERO",
            "session_id": "sess-1",
            "usuario": "Caja-1",
        }

    def test_unlock_returns_session_and_usuario(self):
        body = UnlockRequest(pin=settings.PIN_CAJERO, rol="CAJERO", usuario="Caja-1")
        with patch("routers.auth.log_audit_event", lambda *args, **kwargs: None):
            res = auth_router.unlock(body, _dummy_request("/auth/unlock"))
        self.assertTrue(res.token)
        self.assertEqual(res.usuario, "Caja-1")
        self.assertTrue(res.session_id)

    def test_auth_lockout(self):
        bad_pin = "0001" if settings.PIN_CAJERO != "0001" else "0002"
        req = _dummy_request("/auth/unlock")
        with patch("routers.auth.log_audit_event", lambda *args, **kwargs: None):
            for _ in range(max(settings.AUTH_MAX_ATTEMPTS - 1, 0)):
                with self.assertRaises(HTTPException) as ctx:
                    auth_router.unlock(UnlockRequest(pin=bad_pin, rol="CAJERO"), req)
                self.assertEqual(ctx.exception.status_code, 401)

            with self.assertRaises(HTTPException) as ctx:
                auth_router.unlock(UnlockRequest(pin=bad_pin, rol="CAJERO"), req)
            self.assertEqual(ctx.exception.status_code, 429)

    def test_unlock_blocks_when_active_sessions_limit_reached(self):
        req = _dummy_request("/auth/unlock")
        with (
            patch("routers.auth.log_audit_event", lambda *args, **kwargs: None),
            patch.object(settings, "AUTH_MAX_ACTIVE_SESSIONS", 2),
        ):
            auth_router.unlock(UnlockRequest(pin=settings.PIN_CAJERO, rol="CAJERO", usuario="Caja-A"), req)
            auth_router.unlock(UnlockRequest(pin=settings.PIN_CAJERO, rol="CAJERO", usuario="Caja-B"), req)
            with self.assertRaises(HTTPException) as ctx:
                auth_router.unlock(UnlockRequest(pin=settings.PIN_CAJERO, rol="CAJERO", usuario="Caja-C"), req)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_logout_revokes_active_session(self):
        with patch("routers.auth.log_audit_event", lambda *args, **kwargs: None):
            unlock_res = auth_router.unlock(
                UnlockRequest(pin=settings.PIN_CAJERO, rol="CAJERO", usuario="Caja-1"),
                _dummy_request("/auth/unlock"),
            )
            user = get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=unlock_res.token)
            )
            auth_router.logout(_dummy_request("/auth/logout"), user)
            with self.assertRaises(HTTPException) as ctx:
                get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=unlock_res.token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rbac_blocks_cajero_admin_guard(self):
        guard = require_roles("ADMIN")
        with self.assertRaises(HTTPException) as ctx:
            guard(self.user_ctx)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_sales_are_idempotent_by_client_sale_id(self):
        fake_sb = FakeSupabase()
        sale_id = str(uuid.uuid4())
        payload = VentaCreate.model_validate(
            {
                "client_sale_id": sale_id,
                "items": [
                    {
                        "producto_id": 1,
                        "nombre_snapshot": "Latte",
                        "precio_unitario": 55,
                        "cantidad": 1,
                        "modificadores_snapshot": [],
                    }
                ],
                "pago": {"metodo": "EFECTIVO", "monto": 55, "recibido": 60},
                "total": 55,
            }
        )
        req = _dummy_request("/comandas")
        with (
            patch("routers.comandas.get_supabase", lambda: fake_sb),
            patch("routers.comandas.log_audit_event", lambda *args, **kwargs: None),
        ):
            first = comandas_router.crear_venta(payload, req, self.user_ctx)
            second = comandas_router.crear_venta(payload, req, self.user_ctx)
        self.assertEqual(first.comanda_id, second.comanda_id)
        self.assertTrue(second.deduplicated)

    def test_sales_require_open_shift(self):
        fake_sb = FakeSupabase(no_jornada=True)
        payload = VentaCreate.model_validate(
            {
                "client_sale_id": str(uuid.uuid4()),
                "items": [
                    {
                        "producto_id": 1,
                        "nombre_snapshot": "Latte",
                        "precio_unitario": 55,
                        "cantidad": 1,
                        "modificadores_snapshot": [],
                    }
                ],
                "pago": {"metodo": "EFECTIVO", "monto": 55, "recibido": 60},
                "total": 55,
            }
        )
        with (
            patch("routers.comandas.get_supabase", lambda: fake_sb),
            patch("routers.comandas.log_audit_event", lambda *args, **kwargs: None),
        ):
            with self.assertRaises(HTTPException) as ctx:
                comandas_router.crear_venta(payload, _dummy_request("/comandas"), self.user_ctx)
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
