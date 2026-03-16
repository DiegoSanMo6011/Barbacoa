import { create } from 'zustand';
import { db, GastoLocal } from '../db/localDB';
import { v4 as uuidv4 } from 'uuid';
import { encolarOperacion } from '../sync/syncQueue';

interface GastosState {
    gastos: GastoLocal[];
    cargarGastos: () => Promise<void>;
    registrarGasto: (monto: number, concepto: string, categoria: string, nota: string, metodo_pago: string) => Promise<void>;
}

export const useGastosStore = create<GastosState>((set, get) => ({
    gastos: [],

    cargarGastos: async () => {
        const gastos = await db.gastos.orderBy('fecha').reverse().toArray();
        set({ gastos });
    },

    registrarGasto: async (monto, concepto, categoria, nota, metodo_pago) => {
        const id = uuidv4();
        const fecha = new Date().toISOString();

        const gasto: GastoLocal = {
            id,
            monto,
            concepto,
            categoria,
            nota,
            metodo_pago,
            fecha,
            sincronizado: false
        };

        // 1. Guardar local optimista
        await db.gastos.add(gasto);

        // 2. Encolar para sync Edge
        await encolarOperacion("GASTO", {
            monto,
            concepto,
            categoria,
            nota,
            metodo_pago
        }, id, Date.now());

        // 3. Recargar estado UI
        await get().cargarGastos();
    }
}));
