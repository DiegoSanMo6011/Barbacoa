/**
 * VentaRapida — Flujo principal POS
 * Interfaz premium usando las clases heredadas de POS_Autonoma
 */
import { useEffect, useMemo, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { Plus, ShoppingCart, CheckCircle, Search, Trash2, WifiOff, Wifi } from 'lucide-react'
import { db, CategoriaLocal, ProductoLocal, ItemCarrito } from '../db/localDB'
import { useVentaStore } from '../store/ventaStore'
import ModificadorModal from '../components/ModificadorModal'
import CobrarModal from '../components/CobrarModal'
import './Comandas.css'

const CATEGORY_COLORS = ['#dc2626', '#16a34a', '#2563eb', '#ca8a04', '#9333ea', '#ea580c']

function categoryColor(category: string) {
    if (!category) return CATEGORY_COLORS[0]
    let hash = 0
    for (let index = 0; index < category.length; index += 1) {
        hash = ((hash << 5) - hash) + category.charCodeAt(index)
        hash |= 0
    }
    return CATEGORY_COLORS[Math.abs(hash) % CATEGORY_COLORS.length]
}

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

const normalizar = (txt: string) =>
    txt.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()

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
    return 0
}

export default function VentaRapida() {
    const [categoriaActiva, setCategoriaActiva] = useState<number | null>(null)
    const [busqueda, setBusqueda] = useState('')
    const [activeTab, setActiveTab] = useState<'catalogo' | 'comanda'>('catalogo')

    // Modals state
    const [productoSeleccionado, setProductoSeleccionado] = useState<ProductoLocal | null>(null)
    const [precioBaseSeleccionado, setPrecioBaseSeleccionado] = useState<number | null>(null)
    const [mostrarCobrar, setMostrarCobrar] = useState(false)
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
        const toOnline = () => setIsOnline(true)
        const toOffline = () => setIsOnline(false)
        window.addEventListener('online', toOnline)
        window.addEventListener('offline', toOffline)
        return () => {
            window.removeEventListener('online', toOnline)
            window.removeEventListener('offline', toOffline)
        }
    }, [])

    const productosVisibles = useMemo(() => {
        const q = busqueda.trim()
        if (!q) {
            const cat = categorias.find(c => c.id === categoriaActiva)
            return (cat?.productos ?? []).map(p => ({
                producto: p,
                categoria_nombre: cat?.nombre ?? '',
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
    }, [busqueda, categoriaActiva, categorias])

    const itemsCount = useMemo(
        () => carrito.reduce((sum, item) => sum + item.cantidad, 0),
        [carrito]
    )

    const solicitarPrecioAbierto = (p: ProductoLocal): number | null => {
        const sugerido = p.precio_base > 0 ? String(p.precio_base) : ''
        const raw = window.prompt(`Precio para "${p.nombre}"`, sugerido)
        if (raw === null) return null
        const valor = Number(raw.replace(',', '.'))
        if (!Number.isFinite(valor) || valor < 0) {
            window.alert('Precio inválido.')
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
            // En móvil, si lo agregan quizás queramos cambiar a comanda, 
            // pero para carga rápida mejor se quedan en catalogo.
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
        setActiveTab('catalogo')
    }

    return (
        <div className="comandas-layout" style={{ height: '100%' }}>

            {/* Panel Izquierdo: Catálogo */}
            <section className={`panel-catalogo ${activeTab === 'catalogo' ? 'active' : ''}`}>
                <div className="catalog-toolbar">
                    <div className="category-bar">
                        {categorias.map(cat => (
                            <button
                                key={cat.id}
                                className={`category-pill ${categoriaActiva === cat.id ? 'active' : ''}`}
                                onClick={() => setCategoriaActiva(cat.id)}
                            >
                                {cat.nombre}
                            </button>
                        ))}
                    </div>
                    <div className="quick-controls">
                        <label className="quick-field">
                            <Search size={16} style={{ color: 'var(--color-text-muted)', position: 'absolute', left: 10, top: 12 }} />
                            <input
                                className="input"
                                type="search"
                                placeholder="Buscar..."
                                value={busqueda}
                                onChange={e => setBusqueda(e.target.value)}
                                style={{ paddingLeft: 34, minWidth: 160 }}
                            />
                        </label>
                    </div>
                </div>

                <div className="products-grid">
                    {productosVisibles.length === 0 && categorias.length > 0 && (
                        <div className="empty-state" style={{ gridColumn: '1 / -1' }}>
                            <p>No se encontraron productos.</p>
                        </div>
                    )}
                    {productosVisibles.map(({ producto: p, categoria_nombre }) => {
                        const inCart = carrito.find(item => item.producto_id === p.id)
                        const isModificable = p.modificadores.length > 0
                        return (
                            <article
                                key={p.id}
                                className={`product-card ${inCart ? 'in-cart' : ''}`}
                                style={{ '--category-accent': categoryColor(categoria_nombre) } as React.CSSProperties}
                            >
                                <div className="product-head">
                                    <span className="product-cat">{categoria_nombre}</span>
                                    {inCart && (
                                        <span className="product-qty-badge">
                                            {inCart.cantidad}
                                        </span>
                                    )}
                                </div>
                                <h3 className="product-name">
                                    {p.personalizacion_tipo === 'TORTA' ? '🎂 ' : ''}
                                    {p.nombre}
                                    {isModificable && ' ✨'}
                                </h3>
                                <div className="product-price">
                                    {p.precio_abierto ? 'Precio Abierto' : fmtMXN(p.precio_base)}
                                </div>
                                <button className="btn btn-primary product-add-btn" onClick={() => handleTapProducto(p)}>
                                    <Plus size={16} /> Agregar
                                </button>
                            </article>
                        )
                    })}
                </div>
            </section>

            {/* Panel Derecho: Carrito (Comanda) */}
            <section className={`panel-comanda ${activeTab === 'comanda' ? 'active' : ''}`}>
                <div className="comanda-header">
                    <div>
                        <h2 className="comanda-title">
                            Caja de Cobro
                        </h2>
                        <p className="comanda-summary">{carrito.length} productos · {itemsCount} piezas</p>
                    </div>
                    <div className="comanda-fields" style={{ justifyContent: 'flex-end' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', fontWeight: 600, color: isOnline ? 'var(--color-success)' : 'var(--color-warning)' }}>
                            {isOnline ? <Wifi size={16} /> : <WifiOff size={16} />}
                            {isOnline ? 'Online' : 'Offline'}
                        </div>
                    </div>
                </div>

                <div className="comanda-items">
                    {carrito.length === 0 ? (
                        <div className="empty-state" style={{ flex: 1 }}>
                            <ShoppingCart size={36} style={{ opacity: 0.3 }} />
                            <p>Agrega productos del catálogo</p>
                        </div>
                    ) : (
                        <div className="items-table-wrap">
                            <table className="items-table">
                                <thead>
                                    <tr>
                                        <th>Quitar</th>
                                        <th>Cant</th>
                                        <th>Sumar</th>
                                        <th>Producto</th>
                                        <th>P.Unit</th>
                                        <th>Subtotal</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {carrito.map(item => (
                                        <tr key={item.uid}>
                                            <td>
                                                <button className="qty-btn" onClick={() => actualizarCantidad(item.uid, item.cantidad - 1)}>
                                                    −
                                                </button>
                                            </td>
                                            <td style={{ textAlign: 'center', fontWeight: 600 }}>
                                                {item.cantidad}
                                            </td>
                                            <td>
                                                <button className="qty-btn" onClick={() => actualizarCantidad(item.uid, item.cantidad + 1)}>
                                                    +
                                                </button>
                                            </td>
                                            <td>
                                                <div className="item-name-wrap">
                                                    <span className="ci-name">{item.nombre_snapshot}</span>
                                                    {item.modificadores_snapshot.length > 0 && (
                                                        <div className="gramos-chips" style={{ marginTop: 4, display: 'block', fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                                                            {item.modificadores_snapshot.map(m => (
                                                                <span key={m.grupo} style={{ display: 'block' }}>
                                                                    {m.grupo}: {m.opcion}{m.delta > 0 ? ` (+${fmtMXN(m.delta)})` : ''}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            </td>
                                            <td>{fmtMXN(item.precio_unitario)}</td>
                                            <td style={{ fontWeight: 700 }}>{fmtMXN(item.precio_unitario * item.cantidad)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                <div className="comanda-footer">
                    <div className="comanda-total">
                        <span>TOTAL</span>
                        <span className="price-lg">{fmtMXN(total)}</span>
                    </div>
                    <div className="footer-actions">
                        <button className="btn btn-danger" onClick={limpiarCarrito} disabled={!carrito.length}>
                            <Trash2 size={16} /> Vaciar
                        </button>
                        <button className="btn btn-success btn-lg" onClick={() => setMostrarCobrar(true)} disabled={!carrito.length}>
                            <CheckCircle size={20} /> Cobrar {fmtMXN(total)}
                        </button>
                    </div>
                </div>
            </section>

            {/* Mobile Bottom Tabs */}
            <nav className="mobile-tabs">
                <button className={`tab-btn ${activeTab === 'catalogo' ? 'active' : ''}`} onClick={() => setActiveTab('catalogo')}>
                    <Plus size={18} />
                    Catálogo
                </button>
                <button className={`tab-btn ${activeTab === 'comanda' ? 'active' : ''}`} onClick={() => setActiveTab('comanda')}>
                    <ShoppingCart size={18} />
                    Carrito
                    {itemsCount > 0 && <span className="tab-badge">{itemsCount}</span>}
                </button>
            </nav>

            {/* Modales */}
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
