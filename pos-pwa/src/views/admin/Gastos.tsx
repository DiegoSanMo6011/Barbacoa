import { useEffect, useState } from 'react'
import { Wallet, PlusCircle } from 'lucide-react'
import { useGastosStore } from '../../store/gastosStore'

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

export default function Gastos() {
    const { gastos, cargarGastos, registrarGasto } = useGastosStore()
    const [monto, setMonto] = useState('')
    const [concepto, setConcepto] = useState('')
    const [categoria, setCategoria] = useState('OPERATIVO')
    const [nota, setNota] = useState('')
    const [metodo, setMetodo] = useState('EFECTIVO')

    useEffect(() => {
        void cargarGastos()
    }, [cargarGastos])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!monto || !concepto) return
        await registrarGasto(parseFloat(monto), concepto, categoria, nota, metodo)
        setMonto('')
        setConcepto('')
        setNota('')
    }

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', padding: 'var(--space-4)', overflowY: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                <Wallet size={28} style={{ color: 'var(--color-brand)' }} />
                <h2 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0 }}>Gestión de Gastos</h2>
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
                        <PlusCircle size={18} /> Registrar Gasto
                    </h3>
                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                            Monto (MXN)
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
                            Concepto
                            <input
                                className="input"
                                placeholder="Ej. Papel de baño, Refrescos..."
                                value={concepto}
                                onChange={e => setConcepto(e.target.value)}
                                required
                            />
                        </label>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                                Categoría
                                <select className="input" value={categoria} onChange={e => setCategoria(e.target.value)}>
                                    <option value="OPERATIVO">Operativo</option>
                                    <option value="INSUMOS">Insumos extras</option>
                                    <option value="MANTENIMIENTO">Mantenimiento</option>
                                    <option value="OTRO">Otro</option>
                                </select>
                            </label>
                            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                                Método
                                <select className="input" value={metodo} onChange={e => setMetodo(e.target.value)}>
                                    <option value="EFECTIVO">Efectivo Caja</option>
                                    <option value="TARJETA">Tarjeta</option>
                                    <option value="TRANSFER">Transferencia</option>
                                </select>
                            </label>
                        </div>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                            Notas
                            <textarea
                                className="input"
                                placeholder="Detalles adicionales (opcional)"
                                value={nota}
                                onChange={e => setNota(e.target.value)}
                                rows={2}
                            />
                        </label>
                        <button className="btn btn-primary" type="submit" style={{ marginTop: 'var(--space-2)' }}>
                            Guardar Gasto
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
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Historial de Gastos</h3>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ minWidth: 600, width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                            <thead style={{ background: 'var(--color-surface)', borderBottom: '2px solid var(--color-border)' }}>
                                <tr>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Cpto.</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Cat.</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Fecha</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Método</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Sync</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600, textAlign: 'right' }}>Monto</th>
                                </tr>
                            </thead>
                            <tbody>
                                {gastos.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-faint)' }}>
                                            No hay gastos registrados localmente.
                                        </td>
                                    </tr>
                                ) : (
                                    gastos.map(g => (
                                        <tr key={g.id} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                                            <td style={{ padding: 'var(--space-3)', fontWeight: 600 }}>{g.concepto}</td>
                                            <td style={{ padding: 'var(--space-3)' }}>
                                                <span style={{ background: 'var(--color-surface-2)', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem', fontWeight: 700 }}>
                                                    {g.categoria}
                                                </span>
                                            </td>
                                            <td style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)' }}>{new Date(g.fecha).toLocaleString()}</td>
                                            <td style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)' }}>{g.metodo_pago}</td>
                                            <td style={{ padding: 'var(--space-3)', textAlign: 'center' }}>{g.sincronizado ? '🟢' : '⚪'}</td>
                                            <td style={{ padding: 'var(--space-3)', textAlign: 'right', fontWeight: 700 }}>{fmtMXN(g.monto)}</td>
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
