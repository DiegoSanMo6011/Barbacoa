"""Operaciones offline con polimorfismo.

Cada operacion sabe como aplicarse contra un destino de sincronizacion.
Esto evita cadenas largas de if/elif en el proceso de sync.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Protocol


class OfflineSync(Protocol):
    """Contrato que debe implementar el servicio que sincroniza offline."""

    def sync_gasto(self, payload: dict) -> None:
        raise NotImplementedError

    def sync_propina(self, payload: dict) -> None:
        raise NotImplementedError

    def sync_cierre(self, payload: dict) -> None:
        raise NotImplementedError

    def sync_comanda(self, payload: dict) -> None:
        raise NotImplementedError


class OfflineOperation(ABC):
    """Operacion offline base."""

    op_type: ClassVar[str]

    def __init__(self, payload: dict):
        self.payload = payload

    @abstractmethod
    def apply(self, target: OfflineSync) -> None:
        raise NotImplementedError

    def record_op(self) -> str:
        return self.op_type

    def to_dict(self) -> dict:
        return {"op": self.record_op(), "payload": self.payload}


_OP_REGISTRY: dict[str, type[OfflineOperation]] = {}


def register_operation(cls: type[OfflineOperation]) -> type[OfflineOperation]:
    _OP_REGISTRY[cls.op_type] = cls
    return cls


@register_operation
class GastoOperation(OfflineOperation):
    op_type = "gasto"

    def apply(self, target: OfflineSync) -> None:
        target.sync_gasto(self.payload)


@register_operation
class PropinaOperation(OfflineOperation):
    op_type = "propina"

    def apply(self, target: OfflineSync) -> None:
        target.sync_propina(self.payload)


@register_operation
class CierreOperation(OfflineOperation):
    op_type = "cierre"

    def apply(self, target: OfflineSync) -> None:
        target.sync_cierre(self.payload)


@register_operation
class ComandaOperation(OfflineOperation):
    op_type = "comanda"

    def apply(self, target: OfflineSync) -> None:
        target.sync_comanda(self.payload)


class UnknownOperation(OfflineOperation):
    op_type = "UNKNOWN"

    def __init__(self, op_name: str, payload: dict):
        super().__init__(payload)
        self._op_name = op_name

    def record_op(self) -> str:
        return self._op_name

    def apply(self, target: OfflineSync) -> None:
        raise ValueError(f"Operacion offline desconocida: {self._op_name}")


def operation_from_record(op_name: str, payload: dict) -> OfflineOperation:
    op_class = _OP_REGISTRY.get(op_name)
    if not op_class:
        return UnknownOperation(op_name, payload)
    return op_class(payload)


@dataclass(frozen=True, slots=True)
class OfflineRecord:
    record_id: int
    operation: OfflineOperation
    created_at: str

    def to_dict(self) -> dict:
        data = {"id": self.record_id, "created_at": self.created_at}
        data.update(self.operation.to_dict())
        return data
