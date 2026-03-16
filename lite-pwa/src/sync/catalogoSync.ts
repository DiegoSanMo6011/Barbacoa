import { db, CategoriaLocal, InsumoLocal, RecetaLocal, GastoLocal, PropinaLocal } from "../db/localDB";
import { apiFetch } from "../lib/api";

function normalizarCatalogo(categoriasRaw: any[]): CategoriaLocal[] {
    if (!Array.isArray(categoriasRaw)) return [];
    return categoriasRaw.map((cat) => ({
        ...cat,
        productos: Array.isArray(cat?.productos)
            ? cat.productos.map((p: any) => ({
                ...p,
                precio_abierto: Boolean(p?.precio_abierto),
                personalizacion_tipo: (p?.personalizacion_tipo ?? "NINGUNA") as "NINGUNA" | "TACO" | "TORTA",
                modificadores: Array.isArray(p?.modificadores) ? p.modificadores : [],
            }))
            : [],
    }));
}

// Preload del catálogo desde el Edge al iniciar la app
export async function sincronizarCatalogo(): Promise<void> {
    try {
        const [
            resCatalogo,
            resInsumos,
            resRecetas,
            resGastos,
            resPropinas
        ] = await Promise.all([
            apiFetch("/productos", {}, { timeoutMs: 8_000 }),
            apiFetch("/inventario/insumos", {}, { timeoutMs: 8_000 }),
            apiFetch("/inventario/recetas", {}, { timeoutMs: 8_000 }),
            apiFetch("/gastos", {}, { timeoutMs: 8_000 }),
            apiFetch("/propinas", {}, { timeoutMs: 8_000 })
        ]);

        if (resCatalogo.ok) {
            const catalogo = await resCatalogo.json();
            const categorias: CategoriaLocal[] = normalizarCatalogo(catalogo.categorias ?? []);
            await db.transaction("rw", db.catalogo, async () => {
                await db.catalogo.clear();
                if (categorias.length > 0) {
                    await db.catalogo.bulkPut(categorias);
                }
            });
        }

        if (resInsumos.ok) {
            const insumos: InsumoLocal[] = await resInsumos.json();
            await db.transaction("rw", db.insumos, async () => {
                await db.insumos.clear();
                if (insumos.length > 0) await db.insumos.bulkPut(insumos);
            });
        }

        if (resRecetas.ok) {
            const recetas: RecetaLocal[] = await resRecetas.json();
            await db.transaction("rw", db.recetas, async () => {
                await db.recetas.clear();
                if (recetas.length > 0) await db.recetas.bulkPut(recetas);
            });
        }

        if (resGastos.ok) {
            const gastos: GastoLocal[] = await resGastos.json();
            await db.transaction("rw", db.gastos, async () => {
                await db.gastos.clear();
                // We add sincronizado assuming these come from the server
                if (gastos.length > 0) await db.gastos.bulkPut(gastos.map(g => ({ ...g, sincronizado: true })));
            });
        }

        if (resPropinas.ok) {
            const propinas: PropinaLocal[] = await resPropinas.json();
            await db.transaction("rw", db.propinas, async () => {
                await db.propinas.clear();
                if (propinas.length > 0) await db.propinas.bulkPut(propinas.map(p => ({ ...p, sincronizada: true })));
            });
        }

    } catch {
        // Sin red: se usa el catálogo cacheado en IndexedDB
        console.info("[Sync] Sin red al sincronizar catálogo/inventario — usando cache local");
    }
}
