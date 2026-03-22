import { useEffect, useState } from 'react'
import { useInventarioStore } from '../../store/inventarioStore'
import { useCatalogoStore } from '../../store/catalogoStore'

export default function Inventario() {
    const { insumos, recetas, cargarInsumos, cargarRecetas, crearInsumo, ajustarStock, guardarRecetasProducto } = useInventarioStore()
    const { categorias, cargarCatalogo } = useCatalogoStore()
    const [tab, setTab] = useState<'INSUMOS' | 'MOVIMIENTOS' | 'RECETAS'>('INSUMOS')

    // Form Insumo
    const [nombreNuevo, setNombreNuevo] = useState('')
    const [unidadNueva, setUnidadNueva] = useState('pz')

    // Form Movimiento
    const [movInsumoId, setMovInsumoId] = useState('')
    const [movTipo, setMovTipo] = useState<'ENTRADA' | 'SALIDA'>('ENTRADA')
    const [movUnidad, setMovUnidad] = useState('pz')
    const [movCantidad, setMovCantidad] = useState('')
    const [movEquiv, setMovEquiv] = useState('') // For unit conversion prompt

    // Editor Recetas
    const [productoSeleccionado, setProductoSeleccionado] = useState<any>(null)
    const [recetaDraft, setRecetaDraft] = useState<any[]>([])
    const [recetaInsumoId, setRecetaInsumoId] = useState('')
    const [recetaCantidad, setRecetaCantidad] = useState('')
    const [recetaUnidad, setRecetaUnidad] = useState('pz')

    useEffect(() => {
        void cargarInsumos()
        void cargarCatalogo()
    }, [cargarInsumos, cargarCatalogo])

    const handleCrearInsumo = async (e: React.FormEvent) => {
        e.preventDefault()
        try {
            await crearInsumo(nombreNuevo, unidadNueva, 0)
            setNombreNuevo('')
        } catch (error: any) {
            alert(error.message)
        }
    }

    const handleAjuste = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!movInsumoId || !movCantidad) return

        const insumo = insumos.find(i => i.id === movInsumoId)
        if (!insumo) return

        let qty = parseFloat(movCantidad)

        // Conversión de unidades (igual que Python CustomTkinter)
        if (movUnidad !== insumo.unidad) {
            if ((movUnidad === 'kg' && insumo.unidad === 'g') || (movUnidad === 'l' && insumo.unidad === 'ml') || (movUnidad === 'pz' && insumo.unidad === 'pz_fraction')) {
                qty = qty * 1000 // A simplificated heuristic, usually UI should handle proper prompts.
            } else if ((movUnidad === 'g' && insumo.unidad === 'kg') || (movUnidad === 'ml' && insumo.unidad === 'l')) {
                qty = qty / 1000
            } else {
                if (!movEquiv) {
                    const eq = window.prompt(`¿A cuántos ${insumo.unidad} equivale 1 ${movUnidad} de este insumo?`)
                    if (!eq) return
                    qty = qty * parseFloat(eq)
                } else {
                    qty = qty * parseFloat(movEquiv)
                }
            }
        }

        try {
            await ajustarStock(movInsumoId, movTipo, qty, 'Ajuste manual PWA')
            setMovCantidad('')
            setMovEquiv('')
        } catch (error: any) {
            alert(error.message)
        }
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ display: 'flex', background: 'var(--color-bg)', borderBottom: '1px solid var(--color-border)' }}>
                {['INSUMOS', 'MOVIMIENTOS', 'RECETAS'].map(t => (
                    <button
                        key={t}
                        onClick={() => setTab(t as any)}
                        style={{
                            padding: '16px 24px',
                            background: tab === t ? 'var(--color-surface)' : 'transparent',
                            border: 'none',
                            borderBottom: tab === t ? '2px solid var(--color-brand)' : '2px solid transparent',
                            color: tab === t ? 'var(--color-text)' : 'var(--color-text-muted)',
                            fontWeight: 'bold',
                            cursor: 'pointer'
                        }}
                    >
                        {t}
                    </button>
                ))}
            </div>

            <div style={{ flex: 1, padding: 'var(--space-4)', overflowY: 'auto' }}>
                {tab === 'INSUMOS' && (
                    <div style={{ display: 'flex', gap: '24px' }}>
                        <div style={{ flex: 1 }}>
                            <h3>Catálogo de Insumos</h3>
                            <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {insumos.map(i => (
                                    <li key={i.id} style={{ background: 'var(--color-surface)', padding: '12px', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
                                        <div style={{ fontWeight: 'bold' }}>{i.nombre}</div>
                                        <div style={{ fontSize: '0.9em', color: 'var(--color-text-muted)' }}>
                                            Stock: {i.stock_actual} {i.unidad}
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div style={{ flex: 1 }}>
                            <h3>Agregar Insumo</h3>
                            <form onSubmit={handleCrearInsumo} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                <input className="input" placeholder="Nombre" value={nombreNuevo} onChange={e => setNombreNuevo(e.target.value)} required />
                                <select className="input" value={unidadNueva} onChange={e => setUnidadNueva(e.target.value)}>
                                    <option value="pz">Piezas (pz)</option>
                                    <option value="g">Gramos (g)</option>
                                    <option value="kg">Kilos (kg)</option>
                                    <option value="ml">Mililitros (ml)</option>
                                    <option value="l">Litros (l)</option>
                                </select>
                                <button className="btn btn-primary" type="submit">Guardar Insumo</button>
                            </form>
                        </div>
                    </div>
                )}

                {tab === 'MOVIMIENTOS' && (
                    <div style={{ maxWidth: '400px' }}>
                        <h3>Registrar Movimiento de Stock</h3>
                        <form onSubmit={handleAjuste} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px' }}>Insumo</label>
                                <select className="input" value={movInsumoId} onChange={e => setMovInsumoId(e.target.value)} required>
                                    <option value="">Selecciona...</option>
                                    {insumos.map(i => (
                                        <option key={i.id} value={i.id}>{i.nombre} (Stock: {i.stock_actual} {i.unidad})</option>
                                    ))}
                                </select>
                            </div>

                            <div style={{ display: 'flex', gap: '16px' }}>
                                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <input type="radio" name="tipo" checked={movTipo === 'ENTRADA'} onChange={() => setMovTipo('ENTRADA')} />
                                    Entrada
                                </label>
                                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <input type="radio" name="tipo" checked={movTipo === 'SALIDA'} onChange={() => setMovTipo('SALIDA')} />
                                    Salida
                                </label>
                            </div>

                            <div style={{ display: 'flex', gap: '12px' }}>
                                <input className="input" type="number" placeholder="Cantidad" value={movCantidad} onChange={e => setMovCantidad(e.target.value)} step="0.01" required style={{ flex: 1 }} />
                                <select className="input" value={movUnidad} onChange={e => setMovUnidad(e.target.value)} style={{ width: '100px' }}>
                                    <option value="pz">pz</option>
                                    <option value="kg">kg</option>
                                    <option value="g">g</option>
                                    <option value="l">l</option>
                                    <option value="ml">ml</option>
                                </select>
                            </div>

                            <button className="btn btn-primary" type="submit">Aplicar Movimiento (Offline Ready)</button>
                        </form>
                    </div>
                )}

                {tab === 'RECETAS' && (
                    <div style={{ display: 'flex', gap: '24px' }}>
                        <div style={{ flex: 1, borderRight: '1px solid var(--color-border)', paddingRight: '24px' }}>
                            <h3>1. Seleccionar Producto</h3>
                            <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', marginTop: '16px' }}>
                                {categorias.map(cat => (
                                    <div key={cat.id} style={{ minWidth: '180px' }}>
                                        <h4 style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '8px', marginBottom: '8px' }}>{cat.nombre}</h4>
                                        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                                            {cat.productos.map(p => (
                                                <li key={p.id} style={{ marginBottom: '4px' }}>
                                                    <button
                                                        className="btn btn-ghost"
                                                        style={{ width: '100%', textAlign: 'left', background: productoSeleccionado?.id === p.id ? 'var(--color-brand-bg)' : 'transparent', color: productoSeleccionado?.id === p.id ? 'var(--color-brand)' : 'var(--color-text)' }}
                                                        onClick={() => {
                                                            setProductoSeleccionado(p);
                                                            const existentes = recetas.filter(r => r.producto_id === p.id);
                                                            setRecetaDraft(existentes.map(r => ({ insumo_id: r.insumo_id, cantidad: r.cantidad, unidad: r.unidad })));
                                                        }}
                                                    >
                                                        {p.nombre}
                                                    </button>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div style={{ flex: 1 }}>
                            <h3>2. Editor de Receta</h3>
                            {!productoSeleccionado ? (
                                <div style={{ padding: '32px', textAlign: 'center', background: 'var(--color-surface-2)', borderRadius: '8px', color: 'var(--color-text-muted)' }}>
                                    <p>Selecciona un producto a la izquierda para armar su receta detallada.</p>
                                </div>
                            ) : (
                                <div>
                                    <h4 style={{ color: 'var(--color-brand)', marginBottom: '16px', fontSize: '1.2em' }}>
                                        Receta para: {productoSeleccionado.nombre}
                                    </h4>

                                    <div style={{ background: 'var(--color-surface-2)', padding: '16px', borderRadius: '8px', marginBottom: '16px' }}>
                                        <h5>Agregar Insumo a la receta</h5>
                                        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                                            <select className="input" style={{ flex: 2 }} value={recetaInsumoId} onChange={e => setRecetaInsumoId(e.target.value)}>
                                                <option value="">Buscar insumo...</option>
                                                {insumos.map(i => <option key={i.id} value={i.id}>{i.nombre}</option>)}
                                            </select>
                                            <input className="input" style={{ flex: 1 }} type="number" step="0.01" placeholder="Cant." value={recetaCantidad} onChange={e => setRecetaCantidad(e.target.value)} />
                                            <select className="input" style={{ flex: 1 }} value={recetaUnidad} onChange={e => setRecetaUnidad(e.target.value)}>
                                                <option value="pz">pz</option>
                                                <option value="g">g</option>
                                                <option value="kg">kg</option>
                                                <option value="ml">ml</option>
                                                <option value="l">l</option>
                                            </select>
                                            <button className="btn btn-primary" onClick={() => {
                                                if (!recetaInsumoId || !recetaCantidad) return;
                                                setRecetaDraft([...recetaDraft, { insumo_id: parseInt(recetaInsumoId), cantidad: parseFloat(recetaCantidad), unidad: recetaUnidad }]);
                                                setRecetaInsumoId('');
                                                setRecetaCantidad('');
                                            }}>+</button>
                                        </div>
                                    </div>

                                    <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 16px 0' }}>
                                        {recetaDraft.length === 0 ? <p style={{ color: 'var(--color-text-muted)' }}>Esta receta está vacía.</p> : null}
                                        {recetaDraft.map((item, idx) => {
                                            const insumoRef = insumos.find(i => String(i.id) === String(item.insumo_id));
                                            return (
                                                <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', borderBottom: '1px solid var(--color-border)' }}>
                                                    <span>• {insumoRef?.nombre || 'Insumo desconocido'}</span>
                                                    <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                                                        <span style={{ fontWeight: 'bold' }}>{item.cantidad} {item.unidad}</span>
                                                        <button className="btn btn-ghost" style={{ padding: '4px 8px', color: 'var(--color-danger)' }} onClick={() => setRecetaDraft(recetaDraft.filter((_, i) => i !== idx))}>Quitar</button>
                                                    </div>
                                                </li>
                                            );
                                        })}
                                    </ul>

                                    <button
                                        className="btn btn-primary btn-full"
                                        onClick={async () => {
                                            try {
                                                await guardarRecetasProducto(productoSeleccionado.id, recetaDraft);
                                                alert("¡Receta guardada exitosamente!");
                                            } catch (error: any) {
                                                alert(error.message);
                                            }
                                        }}
                                    >
                                        💾 Guardar Receta Oficial
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
