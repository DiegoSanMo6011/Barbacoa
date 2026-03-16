/**
 * ModificadorModal — Selector de modificadores paso a paso (React)
 * Los grupos del producto se muestran secuencialmente.
 * Compatible con seleccion_max=1 (radio) y seleccion_max>1 (checkbox).
 */
import { useState } from 'react'
import { ProductoLocal, GrupoModificadorLocal, ItemCarrito } from '../db/localDB'

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

type Props = {
    producto: ProductoLocal
    precioBaseOverride?: number
    onConfirm: (item: Omit<ItemCarrito, 'uid'>) => void
    onClose: () => void
}

type Seleccion = Record<number, number[]> // grupo_id → [opcion_id, ...]

export default function ModificadorModal({ producto, precioBaseOverride, onConfirm, onClose }: Props) {
    const grupos = [...producto.modificadores].sort((a, b) => a.orden - b.orden)
    const precioBase = typeof precioBaseOverride === 'number' ? precioBaseOverride : producto.precio_base

    const [paso, setPaso] = useState(0)
    const [seleccion, setSeleccion] = useState<Seleccion>(() => {
        // Pre-seleccionar defaults
        const defaults: Seleccion = {}
        grupos.forEach(g => {
            const def = g.opciones.find(o => o.es_default)
            if (def) defaults[g.grupo_id] = [def.id]
        })
        return defaults
    })
    const [cantidad, setCantidad] = useState(1)

    const grupo = grupos[paso]
    const esFinal = paso === grupos.length - 1

    const seleccionadosGrupo = seleccion[grupo.grupo_id] ?? []

    const toggleOpcion = (opcionId: number) => {
        setSeleccion(prev => {
            const actual = prev[grupo.grupo_id] ?? []
            if (grupo.seleccion_max === 1) {
                return { ...prev, [grupo.grupo_id]: [opcionId] }
            }
            const yaSeleccionado = actual.includes(opcionId)
            if (yaSeleccionado) {
                return { ...prev, [grupo.grupo_id]: actual.filter(id => id !== opcionId) }
            }
            if (actual.length >= grupo.seleccion_max) return prev // límite alcanzado
            return { ...prev, [grupo.grupo_id]: [...actual, opcionId] }
        })
    }

    // Precio total acumulado
    const deltaTotal = grupos.reduce((sum, g) => {
        const ids = seleccion[g.grupo_id] ?? []
        return sum + ids.reduce((s, id) => {
            const opt = g.opciones.find(o => o.id === id)
            return s + (opt?.precio_delta ?? 0)
        }, 0)
    }, 0)
    const precioFinal = precioBase + deltaTotal
    const totalItem = precioFinal * cantidad

    const puedeAvanzar = !grupo.obligatorio || seleccionadosGrupo.length > 0

    const handleSiguiente = () => {
        if (!puedeAvanzar) return
        if (esFinal) {
            // Construir snapshot de modificadores
            const snapshot = grupos.flatMap(g => {
                const ids = seleccion[g.grupo_id] ?? []
                return ids.map(id => {
                    const opt = g.opciones.find(o => o.id === id)!
                    return { grupo: g.grupo_nombre, opcion: opt.nombre, delta: opt.precio_delta }
                })
            }).filter(m => m.delta > 0 || m.opcion !== '')

            onConfirm({
                producto_id: producto.id,
                nombre_snapshot: producto.nombre,
                precio_unitario: precioFinal,
                cantidad,
                modificadores_snapshot: snapshot,
            })
        } else {
            setPaso(p => p + 1)
        }
    }

    return (
        <div
            className="modal-overlay"
            onClick={e => { if (e.target === e.currentTarget) onClose() }}
        >
            <div className="modal-card" style={{ padding: 0 }}>

                {/* Header */}
                <div style={{
                    padding: 'var(--space-5) var(--space-5) var(--space-4)',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                }}>
                    <div>
                        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600, marginBottom: 4 }}>
                            ✨ Personalizar
                        </p>
                        <h2 style={{ fontSize: '1.15rem', fontWeight: 800 }}>{producto.nombre}</h2>
                        <p style={{ fontSize: '0.85rem', color: 'var(--color-brand)', fontWeight: 700, marginTop: 2 }}>
                            Precio base: {fmtMXN(precioBase)}
                        </p>
                    </div>
                    <button className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Cerrar">✕</button>
                </div>

                {/* Progress dots */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                    padding: 'var(--space-4) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                }}>
                    {grupos.map((g, idx) => (
                        <button
                            key={g.grupo_id}
                            onClick={() => { if (idx < paso) setPaso(idx) }}
                            style={{
                                width: 28, height: 28,
                                borderRadius: '50%',
                                border: '2px solid',
                                borderColor: idx === paso ? 'var(--color-brand)' : idx < paso ? 'var(--color-success)' : 'var(--color-border)',
                                background: idx === paso ? 'var(--color-brand)' : idx < paso ? 'var(--color-success)' : 'transparent',
                                color: idx <= paso ? '#fff' : 'var(--color-text-muted)',
                                fontWeight: 700,
                                fontSize: '0.75rem',
                                cursor: idx < paso ? 'pointer' : 'default',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}
                        >
                            {idx < paso ? '✓' : idx + 1}
                        </button>
                    ))}
                    <span style={{ marginLeft: 'var(--space-2)', fontWeight: 600, fontSize: '0.9rem' }}>
                        {grupo.grupo_nombre}
                        {grupo.obligatorio && <span style={{ color: 'var(--color-danger)', marginLeft: 4 }}>*</span>}
                    </span>
                    {grupo.seleccion_max > 1 && (
                        <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                            máx. {grupo.seleccion_max}
                        </span>
                    )}
                </div>

                {/* Opciones del grupo actual */}
                <div style={{
                    padding: 'var(--space-4) var(--space-5)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-2)',
                    maxHeight: 320,
                    overflowY: 'auto',
                }}>
                    {grupo.opciones.sort((a, b) => a.orden - b.orden).map(opt => {
                        const seleccionado = seleccionadosGrupo.includes(opt.id)
                        return (
                            <button
                                key={opt.id}
                                onClick={() => toggleOpcion(opt.id)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: 'var(--space-3) var(--space-4)',
                                    borderRadius: 'var(--radius)',
                                    border: '2px solid',
                                    borderColor: seleccionado ? 'var(--color-brand)' : 'var(--color-border)',
                                    background: seleccionado ? 'var(--color-brand-bg)' : 'var(--color-surface)',
                                    transition: 'all var(--transition)',
                                    textAlign: 'left',
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{
                                        width: 20, height: 20, borderRadius: grupo.seleccion_max === 1 ? '50%' : 5,
                                        border: '2px solid',
                                        borderColor: seleccionado ? 'var(--color-brand)' : 'var(--color-border)',
                                        background: seleccionado ? 'var(--color-brand)' : 'transparent',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        flexShrink: 0,
                                    }}>
                                        {seleccionado && <span style={{ color: '#fff', fontSize: '0.65rem', fontWeight: 900 }}>✓</span>}
                                    </span>
                                    <span style={{ fontWeight: seleccionado ? 600 : 400, fontSize: '0.9rem' }}>{opt.nombre}</span>
                                </div>
                                {opt.precio_delta > 0 && (
                                    <span style={{ color: 'var(--color-brand)', fontWeight: 700, fontSize: '0.85rem' }}>
                                        +{fmtMXN(opt.precio_delta)}
                                    </span>
                                )}
                            </button>
                        )
                    })}
                </div>

                {/* Footer */}
                <div style={{
                    padding: 'var(--space-4) var(--space-5)',
                    borderTop: '1px solid var(--color-border)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-3)',
                }}>
                    {/* Cantidad */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Cantidad</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            <button
                                onClick={() => setCantidad(c => Math.max(1, c - 1))}
                                style={{ width: 36, height: 36, borderRadius: 'var(--radius)', background: 'var(--color-surface-2)', fontWeight: 700, fontSize: '1.1rem', border: '1px solid var(--color-border)' }}
                            >−</button>
                            <span style={{ fontWeight: 800, fontSize: '1.2rem', minWidth: 24, textAlign: 'center' }}>{cantidad}</span>
                            <button
                                onClick={() => setCantidad(c => c + 1)}
                                style={{ width: 36, height: 36, borderRadius: 'var(--radius)', background: 'var(--color-brand)', color: '#fff', fontWeight: 700, fontSize: '1.1rem', border: 'none' }}
                            >+</button>
                        </div>
                    </div>

                    {/* Total */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                            {fmtMXN(precioFinal)} × {cantidad}
                        </span>
                        <span style={{ fontWeight: 800, fontSize: '1.3rem', color: 'var(--color-brand)' }}>
                            {fmtMXN(totalItem)}
                        </span>
                    </div>

                    {/* CTA */}
                    <button
                        className="btn btn-primary btn-full btn-lg"
                        onClick={handleSiguiente}
                        disabled={!puedeAvanzar}
                    >
                        {esFinal ? '✓ Agregar a la orden' : `Siguiente: ${grupos[paso + 1]?.grupo_nombre} →`}
                    </button>
                </div>
            </div>
        </div>
    )
}
