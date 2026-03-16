import { create } from 'zustand';
import { db, PropinaLocal } from '../db/localDB';
import { v4 as uuidv4 } from 'uuid';
import { encolarOperacion } from '../sync/syncQueue';

interface PropinasState {
    propinas: PropinaLocal[];
    cargarPropinas: () => Promise<void>;
    registrarPropina: (monto: number, fuente: "MESA" | "BARRA" | "DOMICILIO" | "NO_ESPECIFICADO", mesero_id?: string, mesero_nombre?: string, comanda_id?: string) => Promise<void>;
}

export const usePropinasStore = create<PropinasState>((set, get) => ({
    propinas: [],

    cargarPropinas: async () => {
        const propinas = await db.propinas.orderBy('fecha').reverse().toArray();
        set({ propinas });
    },

    registrarPropina: async (monto, fuente, mesero_id, mesero_nombre, comanda_id) => {
        const id = uuidv4();
        const fecha = new Date().toISOString();

        const propina: PropinaLocal = {
            id,
            monto,
            fuente,
            mesero_id,
            mesero_nombre_snapshot: mesero_nombre,
            comanda_id,
            fecha,
            sincronizada: false
        };

        // 1. Guardar local optimista
        await db.propinas.add(propina);

        // 2. Encolar para sync Edge
        await encolarOperacion("PROPINA", {
            monto,
            fuente,
            mesero_id,
            mesero_nombre_snapshot: mesero_nombre,
            comanda_id
        }, id, Date.now());

        // 3. Recargar estado UI
        await get().cargarPropinas();
    }
}));
