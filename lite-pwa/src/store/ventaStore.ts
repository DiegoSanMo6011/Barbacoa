/**
 * Barbacoa POS — Zustand Store
 * Estado global del carrito y sesión de venta
 */
import { create } from "zustand";
import { ItemCarrito } from "../db/localDB";
import { nanoid } from "nanoid"; // añadir via: npm i nanoid

interface VentaState {
    carrito: ItemCarrito[];
    total: number;

    // Acciones del carrito
    agregarItem: (item: Omit<ItemCarrito, "uid">) => void;
    actualizarCantidad: (uid: string, cantidad: number) => void;
    eliminarItem: (uid: string) => void;
    limpiarCarrito: () => void;
}

const calcularTotal = (carrito: ItemCarrito[]) =>
    carrito.reduce((acc, i) => acc + i.precio_unitario * i.cantidad, 0);

export const useVentaStore = create<VentaState>((set) => ({
    carrito: [],
    total: 0,

    agregarItem: (item) =>
        set((state) => {
            const nuevo = { ...item, uid: nanoid() };
            const carrito = [...state.carrito, nuevo];
            return { carrito, total: calcularTotal(carrito) };
        }),

    actualizarCantidad: (uid, cantidad) =>
        set((state) => {
            const carrito =
                cantidad <= 0
                    ? state.carrito.filter((i) => i.uid !== uid)
                    : state.carrito.map((i) =>
                        i.uid === uid ? { ...i, cantidad } : i
                    );
            return { carrito, total: calcularTotal(carrito) };
        }),

    eliminarItem: (uid) =>
        set((state) => {
            const carrito = state.carrito.filter((i) => i.uid !== uid);
            return { carrito, total: calcularTotal(carrito) };
        }),

    limpiarCarrito: () => set({ carrito: [], total: 0 }),
}));
