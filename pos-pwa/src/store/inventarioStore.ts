import { create } from 'zustand';
import { db, InsumoLocal, RecetaLocal } from '../db/localDB';
import { v4 as uuidv4 } from 'uuid';
import { encolarOperacion } from '../sync/syncQueue';

interface InventarioState {
    insumos: InsumoLocal[];
    recetas: RecetaLocal[];
    cargarInsumos: () => Promise<void>;
    cargarRecetas: (productoId?: number) => Promise<void>;

    // Acciones Insumo
    crearInsumo: (nombre: string, unidad: string, stock_minimo: number) => Promise<void>;
    actualizarInsumo: (id: string, updates: Partial<InsumoLocal>) => Promise<void>;
    eliminarInsumo: (id: string) => Promise<void>;

    // Acciones Stock
    ajustarStock: (insumoId: string, tipo: "ENTRADA" | "SALIDA", cantidad: number, motivo: string) => Promise<void>;

    // Acciones Receta
    guardarRecetasProducto: (productoId: number, recetas: Array<{ insumo_id: string, cantidad: number }>) => Promise<void>;
}

export const useInventarioStore = create<InventarioState>((set, get) => ({
    insumos: [],
    recetas: [],

    cargarInsumos: async () => {
        const insumos = await db.insumos.orderBy('nombre').toArray();
        set({ insumos: insumos.filter(i => i.activo) });
    },

    cargarRecetas: async (productoId) => {
        let query = db.recetas.toCollection();
        if (productoId) {
            query = db.recetas.where('producto_id').equals(productoId);
        }
        const recetas = await query.toArray();
        set({ recetas });
    },

    crearInsumo: async (nombre, unidad, stock_minimo) => {
        // En offline-first puro podríamos generar UUID local y encolar, pero para insumos (catálogo base) 
        // a menudo es mejor requerir red para la creación inicial para evitar colisiones de IDs locales vs remotos.
        // Haremos la implementación simple: intentamos guardar directo en API, si falla por red, arrojamos error.
        throw new Error("La creación de insumos requiere conexión a internet por ahora. Implementación pendiente de API Directa.");
    },

    actualizarInsumo: async () => {
        throw new Error("La actualización de insumos requiere conexión a internet por ahora.");
    },

    eliminarInsumo: async () => {
        throw new Error("La eliminación de insumos requiere conexión a internet por ahora.");
    },

    ajustarStock: async (insumoId, tipo, cantidad, motivo) => {
        const insumo = await db.insumos.get(insumoId);
        if (!insumo) throw new Error("Insumo no encontrado");

        // 1. Aplicar cambio optimista local
        const nuevoStock = tipo === "ENTRADA" ? insumo.stock_actual + cantidad : Math.max(0, insumo.stock_actual - cantidad);
        await db.insumos.update(insumoId, { stock_actual: nuevoStock });

        // 2. Encolar operación para el Edge
        const opId = uuidv4();
        await encolarOperacion("INVENTARIO_MOVIMIENTO", {
            insumo_id: insumoId,
            tipo,
            cantidad,
            motivo,
            referencia_id: opId
        }, opId, Date.now());

        // 3. Recargar estado
        await get().cargarInsumos();
    },

    guardarRecetasProducto: async () => {
        throw new Error("La edición de recetas requiere conexión a internet por ahora.");
    }
}));
