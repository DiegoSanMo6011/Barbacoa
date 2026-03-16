/**
 * Barbacoa POS — Cola de sincronización offline
 * Cuando hay red, drena la cola de ventas pendientes hacia el Edge.
 */
import { db } from "../db/localDB";
import { apiFetch } from "../lib/api";

const MAX_INTENTOS = 5;

/** Encola una venta para sincronizar cuando haya red */
export async function encolarVenta(payload: object, ventaCreatedAt: number, clientSaleId: string): Promise<void> {
    await db.ops_pendientes.add({
        tipo: "VENTA",
        client_sale_id: clientSaleId,
        payload: JSON.stringify(payload),
        venta_created_at: ventaCreatedAt,
        intentos: 0,
        created_at: Date.now(),
    });
}

/** Encola una operación genérica (Gasto, Propina, Insumo) */
export async function encolarOperacion(tipo: "GASTO" | "PROPINA" | "INVENTARIO_MOVIMIENTO", payload: object, localId: string, timestamp: number): Promise<void> {
    await db.ops_pendientes.add({
        tipo: tipo,
        client_sale_id: localId, // Usa este campo como ID de referencia
        payload: JSON.stringify(payload),
        venta_created_at: timestamp,
        intentos: 0,
        created_at: Date.now(),
    });
}

/** Drena la cola: envía operaciones pendientes al Edge */
export async function drenaColaSinc(): Promise<void> {
    const pendientes = await db.ops_pendientes
        .where("intentos")
        .below(MAX_INTENTOS)
        .toArray();

    for (const op of pendientes) {
        try {
            let url = "/comandas";
            if (op.tipo === "GASTO") url = "/gastos";
            if (op.tipo === "PROPINA") url = "/propinas";
            if (op.tipo === "INVENTARIO_MOVIMIENTO") url = "/inventario/movimientos";

            const res = await apiFetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: op.payload,
            }, { timeoutMs: 10_000 });

            if (res.ok) {
                const data = await res.json();

                // Actualizar DB local basado en el tipo
                if (op.tipo === "VENTA") {
                    await db.ventas.where("client_sale_id").equals(op.client_sale_id).modify({ sincronizada: true, comanda_id: data.comanda_id });
                } else if (op.tipo === "GASTO") {
                    await db.gastos.where("id").equals(op.client_sale_id).modify({ sincronizado: true });
                } else if (op.tipo === "PROPINA") {
                    await db.propinas.where("id").equals(op.client_sale_id).modify({ sincronizada: true });
                }
                // Para inventario, no almacenamos los movimientos offline permanentemente en IndexedDB, solo cambian el stock directamente o se re-descargan al inicio.

                // Eliminar de la cola
                await db.ops_pendientes.delete(op.id!);
            } else {
                let error = `HTTP ${res.status}`;
                if (res.status === 409) {
                    try {
                        const body = await res.json();
                        if (body?.detail && String(body.detail).toLowerCase().includes("jornada")) {
                            error = String(body.detail);
                            await db.ops_pendientes.update(op.id!, { error });
                            continue;
                        }
                    } catch {
                        // ignore
                    }
                }
                await db.ops_pendientes.update(op.id!, {
                    intentos: op.intentos + 1,
                    error,
                });
            }
        } catch (err) {
            if (String(err).includes("Sesión expirada")) {
                return
            }
            await db.ops_pendientes.update(op.id!, {
                intentos: op.intentos + 1,
                error: String(err),
            });
        }
    }
}

/** Inicia un sincronizador periódico (cada 30 segundos) */
export function iniciarSincronizador(): () => void {
    const id = setInterval(async () => {
        if (navigator.onLine) {
            await drenaColaSinc();
        }
    }, 30_000);

    // También sincronizar al recuperar conexión
    const onOnline = () => drenaColaSinc();
    window.addEventListener("online", onOnline);

    return () => {
        clearInterval(id);
        window.removeEventListener("online", onOnline);
    };
}
