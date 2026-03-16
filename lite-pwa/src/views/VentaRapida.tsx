/**
 * VentaRapida — Flujo principal POS Lite
 * Mobile: visual de cobro seguro (inspirado en design.pen)
 * Desktop: tablero claro con catalogo + carrito
 */
import { useEffect, useMemo, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db, CategoriaLocal, ProductoLocal, ItemCarrito } from '../db/localDB'
import { useVentaStore } from '../store/ventaStore'
import ModificadorModal from '../components/ModificadorModal'
import CobrarModal from '../components/CobrarModal'

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

const normalizar = (txt: string) =>
    txt
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim()

const esSubsecuencia = (query: string, target: string) => {
    let i = 0
    let j = 0
    while (i < query.length && j < target.length) {
        if (query[i] === target[j]) i += 1
        j += 1
    }
    return i === query.length
}

const scoreBusqueda = (queryRaw: string, targetRaw: string) => {
    const query = normalizar(queryRaw)
    const target = normalizar(targetRaw)
    if (!query || !target) return 0

    if (target === query) return 1.4

    const pos = target.indexOf(query)
    if (pos >= 0) return 1.2 - Math.min(pos, 20) * 0.01

    const tokens = query.split(/\s+/).filter(Boolean)
    const tokenHits = tokens.reduce((acc, token) => acc + (target.includes(token) ? 1 : 0), 0)
    if (tokens.length > 0 && tokenHits === tokens.length) return 0.95

    if (esSubsecuencia(query, target)) return 0.65

    const ratio = tokens.length > 0 ? tokenHits / tokens.length : 0
    return ratio >= 0.5 ? 0.45 + ratio * 0.2 : 0
}

export default function VentaRapida() {
    const [categoriaActiva, setCategoriaActiva] = useState<number | null>(null)
    const [busqueda, setBusqueda] = useState('')
    const [productoSeleccionado, setProductoSeleccionado] = useState<ProductoLocal | null>(null)
    const [precioBaseSeleccionado, setPrecioBaseSeleccionado] = useState<number | null>(null)
    const [mostrarCobrar, setMostrarCobrar] = useState(false)
    const [mostrarCarrito, setMostrarCarrito] = useState(false)
    const [mostrarCatalogo, setMostrarCatalogo] = useState(false)
    const [isMobile, setIsMobile] = useState(() =>
        typeof window !== 'undefined' ? window.matchMedia('(max-width: 900px)').matches : false
    )
    const [isOnline, setIsOnline] = useState(() => navigator.onLine)

    const { carrito, total, agregarItem, actualizarCantidad, eliminarItem, limpiarCarrito } = useVentaStore()

    const categorias = useLiveQuery<CategoriaLocal[]>(() =>
        db.catalogo.orderBy('orden').toArray()
    ) ?? []

    useEffect(() => {
        if (categorias.length > 0 && categoriaActiva === null) {
            setCategoriaActiva(categorias[0].id)
        }
    }, [categorias, categoriaActiva])

    useEffect(() => {
        const mql = window.matchMedia('(max-width: 900px)')
        const onResize = (ev?: MediaQueryListEvent) => {
            const matches = ev?.matches ?? mql.matches
            setIsMobile(matches)
            if (!matches) {
                setMostrarCarrito(false)
                setMostrarCatalogo(false)
            }
        }
        onResize()
        if (typeof mql.addEventListener === 'function') {
            mql.addEventListener('change', onResize)
        } else {
            mql.addListener(onResize)
        }

        const toOnline = () => setIsOnline(true)
        const toOffline = () => setIsOnline(false)
        window.addEventListener('online', toOnline)
        window.addEventListener('offline', toOffline)

        return () => {
            if (typeof mql.removeEventListener === 'function') {
                mql.removeEventListener('change', onResize)
            } else {
                mql.removeListener(onResize)
            }
            window.removeEventListener('online', toOnline)
            window.removeEventListener('offline', toOffline)
        }
    }, [])

    const catActual = categorias.find(c => c.id === categoriaActiva)

    const productosVisibles = useMemo(() => {
        const q = busqueda.trim()
        if (!q) {
            return (catActual?.productos ?? []).map(p => ({
                producto: p,
                categoria_nombre: catActual?.nombre ?? '',
            }))
        }

        return categorias
            .flatMap(cat => cat.productos.map(p => ({
                producto: p,
                categoria_nombre: cat.nombre,
                score: scoreBusqueda(q, p.nombre),
            })))
            .filter(x => x.score >= 0.45)
            .sort((a, b) => b.score - a.score || a.producto.nombre.localeCompare(b.producto.nombre))
            .map(({ producto, categoria_nombre }) => ({ producto, categoria_nombre }))
    }, [busqueda, catActual, categorias])

    const itemsCount = useMemo(
        () => carrito.reduce((sum, item) => sum + item.cantidad, 0),
        [carrito]
    )

    const carritoPreview = carrito.slice(0, 2)
    const hasMoreItems = carrito.length > carritoPreview.length

    const solicitarPrecioAbierto = (p: ProductoLocal): number | null => {
        const sugerido = p.precio_base > 0 ? String(p.precio_base) : ''
        const raw = window.prompt(`Precio para "${p.nombre}"`, sugerido)
        if (raw === null) return null
        const valor = Number(raw.replace(',', '.'))
        if (!Number.isFinite(valor) || valor < 0) {
            window.alert('Precio inválido. Ingresa un número mayor o igual a 0.')
            return null
        }
        return valor
    }

    const handleTapProducto = (p: ProductoLocal) => {
        const precioBase = p.precio_abierto ? solicitarPrecioAbierto(p) : p.precio_base
        if (precioBase === null) return

        if (p.modificadores.length > 0) {
            setPrecioBaseSeleccionado(precioBase)
            setProductoSeleccionado(p)
        } else {
            agregarItem({
                producto_id: p.id,
                nombre_snapshot: p.nombre,
                precio_unitario: precioBase,
                cantidad: 1,
                modificadores_snapshot: [],
            })
        }
    }

    const handleConfirmarModificadores = (item: Omit<ItemCarrito, 'uid'>) => {
        agregarItem(item)
        setProductoSeleccionado(null)
        setPrecioBaseSeleccionado(null)
    }

    const handleVentaCompletada = () => {
        limpiarCarrito()
        setMostrarCobrar(false)
        setMostrarCarrito(false)
    }

    const renderGridProductos = (minWidth: number) => (
        <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: 'var(--space-4)',
            display: 'grid',
            gridTemplateColumns: `repeat(auto-fill, minmax(${minWidth}px, 1fr))`,
            gap: 'var(--space-3)',
            alignContent: 'start',
        }}>
            {categorias.length === 0 && (
                <div style={{
                    gridColumn: '1/-1',
                    textAlign: 'center',
                    padding: 'var(--space-8)',
                    color: 'var(--color-text-muted)',
                }}>
                    <p style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>☕</p>
                    <p style={{ fontWeight: 600 }}>Sin catálogo cargado</p>
                    <p style={{ fontSize: '0.85rem', marginTop: 'var(--space-2)' }}>
                        Conecta el Edge Server para sincronizar
                    </p>
                </div>
            )}
            {busqueda.trim() !== '' && categorias.length > 0 && productosVisibles.length === 0 && (
                <div style={{
                    gridColumn: '1/-1',
                    textAlign: 'center',
                    padding: 'var(--space-6)',
                    color: 'var(--color-text-muted)',
                }}>
                    <p style={{ fontWeight: 600 }}>Sin coincidencias</p>
                    <p style={{ fontSize: '0.82rem', marginTop: 'var(--space-2)' }}>
                        Intenta con otro término parecido
                    </p>
                </div>
            )}
            {productosVisibles.map(({ producto: p, categoria_nombre }) => (
                <button
                    key={p.id}
                    onClick={() => handleTapProducto(p)}
                    style={{
                        background: 'var(--color-surface)',
                        border: '1.5px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-4) var(--space-3)',
                        textAlign: 'center',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 'var(--space-2)',
                        transition: 'all var(--transition)',
                        boxShadow: 'var(--shadow-sm)',
                    }}
                    onPointerDown={e => (e.currentTarget.style.transform = 'scale(0.95)')}
                    onPointerUp={e => (e.currentTarget.style.transform = 'scale(1)')}
                    onPointerLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
                >
                    <span style={{ fontSize: '1.6rem' }}>
                        {p.personalizacion_tipo === 'PASTEL' ? '🎂' : p.modificadores.length > 0 ? '✨' : '●'}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: '0.85rem', lineHeight: 1.3 }}>{p.nombre}</span>
                    {busqueda.trim() !== '' && (
                        <span style={{ fontSize: '0.66rem', color: 'var(--color-text-muted)' }}>{categoria_nombre}</span>
                    )}
                    <span style={{ color: 'var(--color-brand)', fontWeight: 700, fontSize: '0.9rem' }}>
                        {p.precio_abierto ? 'Costo abierto' : fmtMXN(p.precio_base)}
                    </span>
                    {(p.modificadores.length > 0 || p.precio_abierto) && (
                        <span style={{ fontSize: '0.65rem', color: 'var(--color-text-faint)' }}>
                            {p.precio_abierto ? 'te pide precio al cobrar' : 'opciones disponibles'}
                        </span>
                    )}
                </button>
            ))}
        </div>
    )

    const renderCarritoEditable = (options?: { compact?: boolean }) => (
        <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: options?.compact ? 'var(--space-2)' : 'var(--space-3)',
        }}>
            {carrito.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 'var(--space-8) var(--space-4)', color: 'var(--color-text-faint)' }}>
                    <p style={{ fontSize: '2rem' }}>🧾</p>
                    <p style={{ fontSize: '0.85rem', marginTop: 'var(--space-3)' }}>Tap un producto para agregar</p>
                </div>
            ) : (
                carrito.map(item => (
                    <div key={item.uid} style={{
                        padding: 'var(--space-3)',
                        borderRadius: 'var(--radius)',
                        background: 'var(--color-surface-2)',
                        marginBottom: 'var(--space-2)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 'var(--space-1)',
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.85rem', flex: 1, paddingRight: 4 }}>
                                {item.nombre_snapshot}
                            </span>
                            <button onClick={() => eliminarItem(item.uid)} style={{ color: 'var(--color-text-faint)', fontSize: '0.9rem' }}>✕</button>
                        </div>

                        {item.modificadores_snapshot.length > 0 && (
                            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                                {item.modificadores_snapshot.map(m => (
                                    <span key={m.grupo} style={{ display: 'block' }}>
                                        {m.grupo}: {m.opcion}{m.delta > 0 ? ` +${fmtMXN(m.delta)}` : ''}
                                    </span>
                                ))}
                            </div>
                        )}

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                                <button
                                    onClick={() => actualizarCantidad(item.uid, item.cantidad - 1)}
                                    style={{
                                        width: 26, height: 26, borderRadius: 6,
                                        background: 'var(--color-border)', fontWeight: 700,
                                    }}
                                >−</button>
                                <span style={{ fontWeight: 700, minWidth: 16, textAlign: 'center', fontSize: '0.9rem' }}>
                                    {item.cantidad}
                                </span>
                                <button
                                    onClick={() => actualizarCantidad(item.uid, item.cantidad + 1)}
                                    style={{
                                        width: 26, height: 26, borderRadius: 6,
                                        background: 'var(--color-brand)', color: '#fff', fontWeight: 700,
                                    }}
                                >+</button>
                            </div>
                            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--color-brand)' }}>
                                {fmtMXN(item.precio_unitario * item.cantidad)}
                            </span>
                        </div>
                    </div>
                ))
            )}
        </div>
    )

    const resumenCard = (
        <section style={{
            borderRadius: 16,
            background: 'var(--color-surface)',
            padding: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
        }}>
            <h3 style={{ fontSize: 24, lineHeight: 1.1, fontWeight: 700, color: 'var(--color-text)' }}>
                Resumen de cobro
            </h3>
            {carritoPreview.length === 0 ? (
                <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Agrega productos para empezar.</p>
            ) : (
                carritoPreview.map(item => (
                    <div key={item.uid} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 14 }}>
                        <span style={{ color: 'var(--color-text)' }}>{item.cantidad} x {item.nombre_snapshot}</span>
                        <span style={{ fontWeight: 700, color: 'var(--color-text)' }}>{fmtMXN(item.precio_unitario * item.cantidad)}</span>
                    </div>
                ))
            )}
            {hasMoreItems && (
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                    + {carrito.length - carritoPreview.length} item(s) mas
                </p>
            )}
            <div style={{ height: 1, background: 'var(--color-border)' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, color: 'var(--color-text)' }}>Total</span>
                <span style={{ fontWeight: 800, fontSize: 22, color: 'var(--color-text)' }}>{fmtMXN(total)}</span>
            </div>
            <button
                className="btn btn-primary btn-full"
                style={{ height: 56, borderRadius: 12, marginTop: 2 }}
                onClick={() => setMostrarCobrar(true)}
                disabled={carrito.length === 0}
            >
                Confirmar cobro {fmtMXN(total)}
            </button>
            <button
                className="btn btn-ghost btn-full"
                style={{ height: 44, borderRadius: 10 }}
                onClick={() => setMostrarCarrito(true)}
            >
                Ver detalle del carrito
            </button>
        </section>
    )

    if (isMobile) {
        return (
            <div style={{
                height: 'calc(100dvh - 88px)',
                background: 'var(--color-bg)',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
            }}>
                {/* Header Compacto */}
                <div style={{
                    padding: 'var(--space-3) var(--space-4)',
                    background: 'var(--color-surface)',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexShrink: 0,
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <span style={{ fontSize: '1.2rem', fontWeight: 800 }}>POS Lite</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', fontSize: '0.85rem', fontWeight: 600 }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-success)' }} />
                            Abierta
                        </span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: isOnline ? 'var(--color-success)' : 'var(--color-warning)' }} />
                            {isOnline ? 'En línea' : 'Local'}
                        </span>
                    </div>
                </div>

                {/* Buscador Fijo */}
                <div style={{
                    padding: 'var(--space-2) var(--space-4)',
                    background: 'var(--color-surface)',
                    borderBottom: '1px solid var(--color-border)',
                    flexShrink: 0,
                }}>
                    <input
                        className="input"
                        type="search"
                        placeholder="🔎 Buscar producto..."
                        value={busqueda}
                        onChange={e => setBusqueda(e.target.value)}
                        style={{ background: 'var(--color-surface-2)', border: 'none' }}
                    />
                </div>

                {/* Categorías (Scroll Horizontal) */}
                <div style={{
                    display: 'flex',
                    gap: 'var(--space-2)',
                    padding: 'var(--space-2) var(--space-4)',
                    overflowX: 'auto',
                    background: 'var(--color-surface)',
                    borderBottom: '1px solid var(--color-border)',
                    flexShrink: 0,
                    msOverflowStyle: 'none',
                    scrollbarWidth: 'none',
                }}>
                    {categorias.map(cat => (
                        <button
                            key={cat.id}
                            onClick={() => setCategoriaActiva(cat.id)}
                            style={{
                                padding: '6px 14px',
                                borderRadius: 99,
                                fontSize: '0.85rem',
                                fontWeight: 600,
                                whiteSpace: 'nowrap',
                                background: categoriaActiva === cat.id ? 'var(--color-brand)' : 'var(--color-surface-2)',
                                color: categoriaActiva === cat.id ? '#fff' : 'var(--color-text-muted)',
                                transition: 'all var(--transition)',
                                border: 'none',
                            }}
                        >
                            {cat.nombre}
                        </button>
                    ))}
                </div>

                {/* Catálogo de Productos */}
                <div style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: 'var(--space-4)',
                    paddingBottom: '100px', // padding para el FAB
                }}>
                    {renderGridProductos(130)}
                </div>

                {/* Floating Action Button (FAB) para el carrito */}
                <div style={{
                    position: 'absolute',
                    bottom: 'var(--space-4)',
                    right: 'var(--space-4)',
                    left: 'var(--space-4)',
                    display: 'flex',
                    justifyContent: 'flex-end',
                    pointerEvents: 'none', // Transparente a clicks para el fondo
                }}>
                    <button
                        className="btn btn-primary shadow-lg"
                        style={{
                            borderRadius: 99,
                            padding: '12px 20px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-3)',
                            pointerEvents: 'auto', // Restaurar clicks para el FAB
                            boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
                            transform: carrito.length > 0 ? 'translateY(0)' : 'translateY(150%)',
                            transition: 'transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                            minWidth: 160,
                            justifyContent: 'space-between',
                        }}
                        onClick={() => setMostrarCarrito(true)}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: '1.2rem' }}>🛒</span>
                            <span style={{ fontWeight: 800, background: 'rgba(255,255,255,0.2)', padding: '2px 8px', borderRadius: 99 }}>
                                {carrito.length}
                            </span>
                        </div>
                        <span style={{ fontWeight: 800, fontSize: '1.05rem' }}>{fmtMXN(total)}</span>
                    </button>
                </div>

                {/* Modal Carrito (Bottom Sheet) */}
                {mostrarCarrito && (
                    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setMostrarCarrito(false) }}>
                        <div className="modal-card" style={{
                            maxHeight: '90dvh',
                            display: 'flex',
                            flexDirection: 'column',
                            width: '100%',
                            margin: 0,
                            borderRadius: '24px 24px 0 0',
                            position: 'absolute',
                            bottom: 0
                        }}>
                            <div style={{
                                padding: 'var(--space-4)',
                                borderBottom: '1px solid var(--color-border)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                            }}>
                                <span style={{ fontWeight: 800, fontSize: '1.1rem' }}>🛒 Orden ({carrito.length})</span>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    {carrito.length > 0 && (
                                        <button
                                            onClick={limpiarCarrito}
                                            style={{ fontSize: '0.85rem', color: 'var(--color-danger)', fontWeight: 600, background: 'none', border: 'none' }}
                                        >
                                            Limpiar
                                        </button>
                                    )}
                                    <button
                                        style={{ width: 32, height: 32, borderRadius: 16, background: 'var(--color-surface-2)', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}
                                        onClick={() => setMostrarCarrito(false)}
                                    >✕</button>
                                </div>
                            </div>

                            {renderCarritoEditable({ compact: true })}

                            <div style={{
                                padding: 'var(--space-4)',
                                borderTop: '1px solid var(--color-border)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 'var(--space-3)',
                                background: 'var(--color-surface)',
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--color-text-muted)' }}>Total a cobrar</span>
                                    <span style={{ fontWeight: 800, fontSize: '1.5rem', color: 'var(--color-brand)' }}>
                                        {fmtMXN(total)}
                                    </span>
                                </div>
                                <button
                                    className="btn btn-primary btn-full"
                                    style={{ height: 56, borderRadius: 16, fontSize: '1.1rem' }}
                                    onClick={() => {
                                        setMostrarCarrito(false)
                                        setMostrarCobrar(true)
                                    }}
                                    disabled={carrito.length === 0}
                                >
                                    Confirmar Cobro →
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {productoSeleccionado && (
                    <ModificadorModal
                        producto={productoSeleccionado}
                        precioBaseOverride={precioBaseSeleccionado ?? undefined}
                        onConfirm={handleConfirmarModificadores}
                        onClose={() => {
                            setProductoSeleccionado(null)
                            setPrecioBaseSeleccionado(null)
                        }}
                    />
                )}

                {mostrarCobrar && (
                    <CobrarModal
                        carrito={carrito}
                        total={total}
                        onCompletado={handleVentaCompletada}
                        onClose={() => setMostrarCobrar(false)}
                    />
                )}
            </div>
        )
    }

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'row' }}>
            <section style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                minWidth: 0,
                minHeight: 0,
            }}>
                <div style={{
                    padding: 'var(--space-4) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-4)',
                }}>
                    <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Punto de Venta</h2>
                    <span style={{
                        padding: '4px 10px',
                        borderRadius: 99,
                        background: 'var(--color-success-bg)',
                        color: 'var(--color-success)',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                    }}>
                        CAJA ABIERTA
                    </span>
                    <div style={{ flex: 1 }} />
                    <input
                        className="input"
                        type="search"
                        placeholder="🔎 Buscar producto..."
                        value={busqueda}
                        onChange={e => setBusqueda(e.target.value)}
                        style={{ width: 280 }}
                    />
                </div>

                <div style={{
                    display: 'flex',
                    gap: 'var(--space-2)',
                    padding: 'var(--space-3) var(--space-5)',
                    overflowX: 'auto',
                    borderBottom: '1px solid var(--color-border)',
                    flexShrink: 0,
                }}>
                    {categorias.map(cat => (
                        <button
                            key={cat.id}
                            onClick={() => setCategoriaActiva(cat.id)}
                            style={{
                                padding: '6px 16px',
                                borderRadius: 99,
                                fontSize: '0.85rem',
                                fontWeight: 600,
                                whiteSpace: 'nowrap',
                                background: categoriaActiva === cat.id ? 'var(--color-brand)' : 'var(--color-surface-2)',
                                color: categoriaActiva === cat.id ? '#fff' : 'var(--color-text-muted)',
                                border: '1.5px solid',
                                borderColor: categoriaActiva === cat.id ? 'var(--color-brand)' : 'var(--color-border)',
                                transition: 'all var(--transition)',
                            }}
                        >
                            {cat.nombre}
                        </button>
                    ))}
                </div>

                {renderGridProductos(150)}
            </section>

            <aside style={{
                width: 380,
                borderLeft: '1.5px solid var(--color-border)',
                display: 'flex',
                flexDirection: 'column',
                background: 'var(--color-surface-2)',
                minHeight: 0,
            }}>
                <div style={{
                    padding: 'var(--space-4)',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: 'var(--color-surface)',
                }}>
                    <span style={{ fontWeight: 700, fontSize: '1.05rem' }}>
                        🛒 Orden en curso
                    </span>
                    <span style={{
                        background: 'var(--color-brand)',
                        color: 'white',
                        padding: '2px 8px',
                        borderRadius: 12,
                        fontSize: '0.75rem',
                        fontWeight: 700,
                    }}>
                        {itemsCount}
                    </span>
                </div>

                {renderCarritoEditable({ compact: true })}

                <div style={{
                    padding: 'var(--space-4)',
                    borderTop: '1px solid var(--color-border)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-3)',
                    background: 'var(--color-surface)',
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--color-text-muted)' }}>Total</span>
                        <span style={{ fontWeight: 800, fontSize: '1.6rem', color: 'var(--color-text)' }}>
                            {fmtMXN(total)}
                        </span>
                    </div>
                    {carrito.length > 0 && (
                        <button
                            onClick={limpiarCarrito}
                            style={{ fontSize: '0.8rem', color: 'var(--color-danger)', fontWeight: 600, textAlign: 'right', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                        >
                            Vaciar carrito
                        </button>
                    )}
                    <button
                        className="btn btn-primary btn-full btn-lg"
                        onClick={() => setMostrarCobrar(true)}
                        disabled={carrito.length === 0}
                        style={{ height: 56, fontSize: '1.1rem' }}
                    >
                        Cobrar {fmtMXN(total)} →
                    </button>
                </div>
            </aside>

            {productoSeleccionado && (
                <ModificadorModal
                    producto={productoSeleccionado}
                    precioBaseOverride={precioBaseSeleccionado ?? undefined}
                    onConfirm={handleConfirmarModificadores}
                    onClose={() => {
                        setProductoSeleccionado(null)
                        setPrecioBaseSeleccionado(null)
                    }}
                />
            )}

            {mostrarCobrar && (
                <CobrarModal
                    carrito={carrito}
                    total={total}
                    onCompletado={handleVentaCompletada}
                    onClose={() => setMostrarCobrar(false)}
                />
            )}
        </div>
    )
}
