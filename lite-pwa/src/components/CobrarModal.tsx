/**
 * CobrarModal — Selección de método de pago y registro de venta
 * Flujo: elegir método → (efectivo: ingresar recibido) → confirmar → ticket
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ItemCarrito, db, VentaLocal } from '../db/localDB'
import { encolarVenta, drenaColaSinc } from '../sync/syncQueue'
import { apiFetch } from '../lib/api'
import { createClientSaleId } from '../lib/sales'

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

type Metodo = 'EFECTIVO' | 'TARJETA' | 'TRANSFER'

type Props = {
    carrito: ItemCarrito[]
    total: number
    onCompletado: () => void
    onClose: () => void
}

const METODOS: { id: Metodo; label: string; emoji: string }[] = [
    { id: 'EFECTIVO', label: 'Efectivo', emoji: '💵' },
    { id: 'TARJETA', label: 'Tarjeta', emoji: '💳' },
    { id: 'TRANSFER', label: 'Transfer', emoji: '📲' },
]

export default function CobrarModal({ carrito, total, onCompletado, onClose }: Props) {
    const navigate = useNavigate()
    const [metodo, setMetodo] = useState<Metodo>('EFECTIVO')
    const [recibido, setRecibido] = useState('')
    const [cargando, setCargando] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [ticket, setTicket] = useState<{ folio?: number; cambio: number } | null>(null)

    const cambio = metodo === 'EFECTIVO'
        ? Math.max(0, parseFloat(recibido || '0') - total)
        : 0

    const puedeConfirmar =
        metodo !== 'EFECTIVO' ||
        (parseFloat(recibido || '0') >= total)

    const persistLocalVenta = async (venta: VentaLocal) => {
        await db.ventas.add(venta)
    }

    const parseErrorDetail = async (res: Response): Promise<string> => {
        try {
            const body = await res.json()
            if (body?.detail) return String(body.detail)
        } catch {
            // ignore
        }
        return `HTTP ${res.status}`
    }

    const handleCobrar = async () => {
        if (!puedeConfirmar) return
        setCargando(true)
        setError(null)

        const clientSaleId = createClientSaleId()
        const ventaCreatedAt = Date.now()

        const payload = {
            client_sale_id: clientSaleId,
            items: carrito.map(i => ({
                producto_id: i.producto_id,
                nombre_snapshot: i.nombre_snapshot,
                precio_unitario: i.precio_unitario,
                cantidad: i.cantidad,
                modificadores_snapshot: i.modificadores_snapshot,
                notas_item: i.notas_item ?? null,
            })),
            pago: {
                metodo,
                monto: total,
                recibido: metodo === 'EFECTIVO' ? parseFloat(recibido) : undefined,
            },
            total,
        }

        const ventaLocal: VentaLocal = {
            client_sale_id: clientSaleId,
            total,
            cambio,
            metodo_pago: metodo,
            items_count: carrito.reduce((s, i) => s + i.cantidad, 0),
            created_at: ventaCreatedAt,
            sincronizada: false,
        }

        if (navigator.onLine) {
            try {
                const res = await apiFetch('/comandas', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                }, { timeoutMs: 8_000 })

                if (res.ok) {
                    const data = await res.json()
                    await persistLocalVenta({
                        ...ventaLocal,
                        sincronizada: true,
                        comanda_id: data.comanda_id,
                        folio: data.folio,
                    })
                    setTicket({ folio: data.folio, cambio })
                } else {
                    const detail = await parseErrorDetail(res)
                    if (res.status === 409 && detail.toLowerCase().includes('jornada')) {
                        setError(detail)
                        setCargando(false)
                        return
                    }
                    await persistLocalVenta(ventaLocal)
                    await encolarVenta(payload, ventaCreatedAt, clientSaleId)
                    setTicket({ cambio })
                }
            } catch {
                await persistLocalVenta(ventaLocal)
                await encolarVenta(payload, ventaCreatedAt, clientSaleId)
                setTicket({ cambio })
            }
        } else {
            await persistLocalVenta(ventaLocal)
            await encolarVenta(payload, ventaCreatedAt, clientSaleId)
            setTicket({ cambio })
        }

        drenaColaSinc().catch(() => { })
        setCargando(false)
    }

    if (ticket) {
        return (
            <div className="modal-overlay">
                <div className="modal-card" style={{ padding: 'var(--space-8)', textAlign: 'center' }}>
                    <div style={{ fontSize: '3.5rem', marginBottom: 'var(--space-4)' }}>✅</div>
                    <h2 style={{ fontWeight: 800, fontSize: '1.4rem', marginBottom: 'var(--space-2)' }}>
                        ¡Venta registrada!
                    </h2>
                    {ticket.folio && (
                        <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-3)' }}>
                            Folio #{ticket.folio}
                        </p>
                    )}
                    {!ticket.folio && (
                        <p style={{ fontSize: '0.8rem', color: 'var(--color-warning)', marginBottom: 'var(--space-3)' }}>
                            ⚠️ Sin conexión — se sincronizará cuando haya red
                        </p>
                    )}

                    <div style={{
                        background: 'var(--color-surface-2)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-4)',
                        textAlign: 'left',
                        marginBottom: 'var(--space-5)',
                    }}>
                        {carrito.map(item => (
                            <div key={item.uid} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: 4 }}>
                                <span>{item.cantidad}× {item.nombre_snapshot}</span>
                                <span style={{ fontWeight: 600 }}>{fmtMXN(item.precio_unitario * item.cantidad)}</span>
                            </div>
                        ))}
                        <div style={{ borderTop: '1px solid var(--color-border)', marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                            <span>Total</span>
                            <span>{fmtMXN(total)}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginTop: 4, color: 'var(--color-text-muted)' }}>
                            <span>Método</span>
                            <span>{metodo}</span>
                        </div>
                        {metodo === 'EFECTIVO' && ticket.cambio > 0 && (
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginTop: 4, color: 'var(--color-success)' }}>
                                <span>Cambio</span>
                                <span>{fmtMXN(ticket.cambio)}</span>
                            </div>
                        )}
                    </div>

                    <button
                        className="btn btn-primary btn-full btn-lg"
                        onClick={onCompletado}
                    >
                        Nueva venta →
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div
            className="modal-overlay"
            onClick={e => { if (e.target === e.currentTarget) onClose() }}
        >
            <div className="modal-card">
                <div style={{
                    padding: 'var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}>
                    <div>
                        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>Cobrar</p>
                        <h2 style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--color-brand)' }}>
                            {fmtMXN(total)}
                        </h2>
                    </div>
                    <button className="btn btn-ghost btn-icon" onClick={onClose}>✕</button>
                </div>

                <div style={{ padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
                    {error && (
                        <div style={{ padding: 'var(--space-3)', background: 'var(--color-danger-bg)', color: 'var(--color-danger)', borderRadius: 'var(--radius)' }}>
                            <div style={{ fontWeight: 700, marginBottom: 6 }}>{error}</div>
                            <button
                                className="btn btn-ghost"
                                onClick={() => {
                                    onClose()
                                    navigate('/corte')
                                }}
                            >
                                Ir a Corte para abrir jornada
                            </button>
                        </div>
                    )}

                    <div>
                        <p style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 'var(--space-3)', color: 'var(--color-text-muted)' }}>
                            MÉTODO DE PAGO
                        </p>
                        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                            {METODOS.map(m => (
                                <button
                                    key={m.id}
                                    className={`metodo-btn ${metodo === m.id ? `selected-${m.id.toLowerCase()}` : ''}`}
                                    onClick={() => setMetodo(m.id)}
                                >
                                    <span style={{ fontSize: '1.4rem', lineHeight: 1 }}>{m.emoji}</span>
                                    {m.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {metodo === 'EFECTIVO' && (
                        <div>
                            <p style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 'var(--space-3)', color: 'var(--color-text-muted)' }}>
                                RECIBIDO
                            </p>
                            <input
                                className="input"
                                type="number"
                                inputMode="decimal"
                                placeholder={fmtMXN(total)}
                                value={recibido}
                                onChange={e => setRecibido(e.target.value)}
                                style={{ fontSize: '1.3rem', fontWeight: 700, height: 60 }}
                                autoFocus
                            />
                            {parseFloat(recibido || '0') >= total && (
                                <div style={{
                                    marginTop: 'var(--space-3)',
                                    padding: 'var(--space-3) var(--space-4)',
                                    borderRadius: 'var(--radius)',
                                    background: 'var(--color-success-bg)',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    fontWeight: 700,
                                    color: 'var(--color-success)',
                                }}>
                                    <span>Cambio</span>
                                    <span>{fmtMXN(cambio)}</span>
                                </div>
                            )}
                        </div>
                    )}

                    <div style={{
                        background: 'var(--color-surface-2)',
                        borderRadius: 'var(--radius)',
                        padding: 'var(--space-3) var(--space-4)',
                        maxHeight: 160,
                        overflowY: 'auto',
                    }}>
                        {carrito.map(item => (
                            <div key={item.uid} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', padding: '3px 0' }}>
                                <span style={{ color: 'var(--color-text-muted)' }}>{item.cantidad}× {item.nombre_snapshot}</span>
                                <span style={{ fontWeight: 600 }}>{fmtMXN(item.precio_unitario * item.cantidad)}</span>
                            </div>
                        ))}
                    </div>

                    <button
                        className="btn btn-primary btn-full btn-lg"
                        onClick={handleCobrar}
                        disabled={!puedeConfirmar || cargando}
                    >
                        {cargando ? '⏳ Procesando...' : `✓ Confirmar ${fmtMXN(total)}`}
                    </button>
                </div>
            </div>
        </div>
    )
}
