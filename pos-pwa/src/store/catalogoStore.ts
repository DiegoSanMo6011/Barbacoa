import { create } from 'zustand';
import { db, CategoriaLocal } from '../db/localDB';

interface CatalogoState {
    categorias: CategoriaLocal[];
    cargarCatalogo: () => Promise<void>;
}

export const useCatalogoStore = create<CatalogoState>((set) => ({
    categorias: [],

    cargarCatalogo: async () => {
        try {
            const categorias = await db.catalogo.toArray();
            set({ categorias });
        } catch (error) {
            console.error("Error cargando catálogo desde IndexedDB:", error);
        }
    }
}));
