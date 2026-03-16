/**
 * Barbacoa POS — Base de datos local (IndexedDB via Dexie)
 * Permite operación 100% offline. Se sincroniza con Supabase en segundo plano.
 */
import Dexie, { Table } from "dexie";

// ---- Tipos ----
export interface OpcionLocal {
    id: number;
    nombre: string;
    precio_delta: number;
    es_default: boolean;
    orden: number;
}

export interface GrupoModificadorLocal {
    grupo_id: number;
    grupo_nombre: string;
    obligatorio: boolean;
    seleccion_max: number;
    orden: number;
    opciones: OpcionLocal[];
}

export interface ProductoLocal {
    id: number;
    nombre: string;
    precio_base: number;
    precio_abierto: boolean;
    personalizacion_tipo: "NINGUNA" | "TACO" | "TORTA";
    descripcion?: string;
    orden_catalogo: number;
    categoria_id: number;
    categoria_nombre: string;
    modificadores: GrupoModificadorLocal[];
}

export interface CategoriaLocal {
    id: number;
    nombre: string;
    orden: number;
    productos: ProductoLocal[];
}

// Ítem en el carrito activo (en memoria vía Zustand, no en IndexedDB)
export interface ItemCarrito {
    uid: string; // UUID local único para este ítem del carrito
    producto_id: number;
    nombre_snapshot: string;
    precio_unitario: number; // precio_base + sum(deltas)
    cantidad: number;
    modificadores_snapshot: { grupo: string; opcion: string; delta: number }[];
    notas_item?: string;
}

// Operación pendiente de sincronización con el servidor
export interface OpPendiente {
    id?: number; // autoincrement
    tipo: "VENTA" | "GASTO" | "PROPINA" | "INVENTARIO_MOVIMIENTO";
    client_sale_id: string; // También usado como UUID genérico para gastos/propinas/movimientos
    payload: string; // JSON serializado de VentaCreate, GastoCreate, etc.
    venta_created_at: number; // correlación con ventas.local.created_at
    intentos: number;
    created_at: number; // timestamp
    error?: string;
}

// Venta registrada localmente (historial rápido offline)
export interface VentaLocal {
    id?: number;
    client_sale_id: string;
    folio?: number;
    comanda_id?: string; // null hasta que se sincronice
    total: number;
    cambio: number;
    metodo_pago: string;
    items_count: number;
    created_at: number;
    sincronizada: boolean;
}

// ---- Inventario & Finanzas Local ----
export interface InsumoLocal {
    id: string;
    nombre: string;
    unidad: string;
    stock_actual: number;
    stock_minimo: number;
    activo: boolean;
}

export interface RecetaLocal {
    id: string;
    producto_id: number;
    insumo_id: string;
    cantidad: number;
}

export interface GastoLocal {
    id: string;
    monto: number;
    concepto: string;
    categoria: string;
    nota?: string;
    metodo_pago: string;
    fecha: string;
    sincronizado: boolean;
}

export interface PropinaLocal {
    id: string;
    monto: number;
    mesero_id?: string;
    mesero_nombre_snapshot?: string;
    fuente: string;
    comanda_id?: string;
    fecha: string;
    sincronizada: boolean;
}

// ---- Clase de base de datos ----
class PosLiteDB extends Dexie {
    catalogo!: Table<CategoriaLocal>;
    ops_pendientes!: Table<OpPendiente>;
    ventas!: Table<VentaLocal>;
    insumos!: Table<InsumoLocal>;
    recetas!: Table<RecetaLocal>;
    gastos!: Table<GastoLocal>;
    propinas!: Table<PropinaLocal>;

    constructor() {
        super("barbacoa-pos");
        this.version(1).stores({
            catalogo: "id, nombre",          // PK = categoria.id
            ops_pendientes: "++id, tipo, created_at",
            ventas: "++id, created_at, sincronizada",
        });
        // v2 agrega índices usados por la app para evitar errores en runtime.
        this.version(2).stores({
            catalogo: "id, nombre, orden",
            ops_pendientes: "++id, tipo, created_at, intentos, venta_created_at",
            ventas: "++id, created_at, sincronizada",
        });
        this.version(3).stores({
            catalogo: "id, nombre, orden",
            ops_pendientes: "++id, tipo, created_at, intentos, venta_created_at, client_sale_id",
            ventas: "++id, created_at, sincronizada, client_sale_id",
        });
        this.version(4).stores({
            catalogo: "id, nombre, orden",
            ops_pendientes: "++id, tipo, created_at, intentos, venta_created_at, client_sale_id",
            ventas: "++id, created_at, sincronizada, client_sale_id",
            insumos: "id, nombre",
            recetas: "id, producto_id, insumo_id",
            gastos: "id, fecha, sincronizado",
            propinas: "id, fecha, sincronizada",
        });
    }
}

export const db = new PosLiteDB();
