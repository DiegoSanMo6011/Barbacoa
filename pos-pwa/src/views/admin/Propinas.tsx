import { useEffect, useState } from 'react'
import { HandCoins, PlusCircle } from 'lucide-react'
import { usePropinasStore } from '../../store/propinasStore'

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

export default function Propinas() {
    const { propinas, cargarPropinas, registrarPropina } = usePropinasStore()
    const [monto, setMonto] = useState('')
    const [fuente, setFuente] = useState<'MESA' | 'BARRA' | 'DOMICILIO' | 'NO_ESPECIFICADO'>('MESA')

    useEffect(() => {
        void cargarPropinas()
    }, [cargarPropinas])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!monto) return
        await registrarPropina(parseFloat(monto), fuente)
        setMonto('')
    }

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', padding: 'var(--space-4)', overflowY: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                <HandCoins size={28} style={{ color: 'var(--color-brand)' }} />
                <h2 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0 }}>Gestión de Propinas</h2>
            </div>

            <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <section style={{
                    flex: '1 1 320px',
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--color-border)',
                    padding: 'var(--space-4)',
                    boxShadow: 'var(--shadow-sm)'
                }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <PlusCircle size={18} /> Registrar Propina Directa
                    </h3>
                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                            Monto Recibido (MXN)
                            <input
                                className="input"
                                type="number"
                                placeholder="0.00"
                                value={monto}
                                onChange={e => setMonto(e.target.value)}
                                step="0.01"
                                required
                            />
                        </label>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                            Fuente / Origen
                            <select className="input" value={fuente} onChange={e => setFuente(e.target.value as any)}>
                                <option value="MESA">Mesa</option>
                                <option value="BARRA">Barra</option>
                                <option value="DOMICILIO">Domicilio</option>
                                <option value="NO_ESPECIFICADO">Sin especificar</option>
                            </select>
                        </label>
                        <button className="btn btn-primary" type="submit" style={{ marginTop: 'var(--space-2)' }}>
                            Guardar Propina
                        </button>
                    </form>
                </section>

                <section style={{
                    flex: '2 1 500px',
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--color-border)',
                    boxShadow: 'var(--shadow-sm)',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column'
                }}>
                    <div style={{ padding: 'var(--space-4)', borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Historial Reciente</h3>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ minWidth: 500, width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                            <thead style={{ background: 'var(--color-surface)', borderBottom: '2px solid var(--color-border)' }}>
                                <tr>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Fecha</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Fuente</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Sync</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600, textAlign: 'right' }}>Monto</th>
                                </tr>
                            </thead>
                            <tbody>
                                {propinas.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-faint)' }}>
                                            No hay propinas registradas localmente.
                                        </td>
                                    </tr>
                                ) : (
                                    propinas.map(p => (
                                        <tr key={p.id} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                                            <td style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)' }}>{new Date(p.fecha).toLocaleString()}</td>
                                            <td style={{ padding: 'var(--space-3)' }}>
                                                <span style={{ background: 'var(--color-surface-2)', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem', fontWeight: 700 }}>
                                                    {p.fuente}
                                                </span>
                                            </td>
                                            <td style={{ padding: 'var(--space-3)', textAlign: 'center' }}>{p.sincronizada ? '🟢' : '⚪'}</td>
                                            <td style={{ padding: 'var(--space-3)', textAlign: 'right', fontWeight: 700 }}>{fmtMXN(p.monto)}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>
        </div>
    )
}
