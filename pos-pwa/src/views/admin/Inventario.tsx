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
                                <button className="btn btn-primary" type="submit">Guardar</button>
                                <p style={{ fontSize: '0.8em', color: 'var(--color-text-muted)' }}>Nota: La creación requiere red.</p>
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
                    <div>
                        <h3>Editor de Recetas</h3>
                        <p style={{ color: 'var(--color-text-muted)' }}>Selecciona un producto del catálogo para gestionar su receta. (Nota: La gestión requiere red en esta versión inicial).</p>
                        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                            {categorias.map(cat => (
                                <div key={cat.id} style={{ minWidth: '200px' }}>
                                    <h4 style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '8px' }}>{cat.nombre}</h4>
                                    <ul style={{ listStyle: 'none', padding: 0 }}>
                                        {cat.productos.map(p => (
                                            <li key={p.id} style={{ padding: '4px 0', fontSize: '0.9em' }}>
                                                {p.nombre}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
