import { useEffect, useState } from 'react'
import { usePropinasStore } from '../../store/propinasStore'

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
        <div style={{ padding: 'var(--space-4)', display: 'flex', gap: 'var(--space-4)', width: '100%', height: '100%' }}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <h2>Registrar Propina Directa</h2>
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    <input
                        className="input"
                        type="number"
                        placeholder="Monto Recibido"
                        value={monto}
                        onChange={e => setMonto(e.target.value)}
                        step="0.01"
                        required
                    />
                    <select className="input" value={fuente} onChange={e => setFuente(e.target.value as any)}>
                        <option value="MESA">Mesa</option>
                        <option value="BARRA">Barra</option>
                        <option value="DOMICILIO">Domicilio</option>
                        <option value="NO_ESPECIFICADO">Sin especificar</option>
                    </select>
                    <button className="btn btn-primary" type="submit">Guardar Propina</button>
                </form>
            </div>

            <div style={{ flex: 2, overflowY: 'auto', background: 'var(--color-surface)', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead style={{ background: 'var(--color-bg)', borderBottom: '1px solid var(--color-border)' }}>
                        <tr>
                            <th style={{ padding: 'var(--space-2)' }}>Fecha</th>
                            <th style={{ padding: 'var(--space-2)' }}>Fuente</th>
                            <th style={{ padding: 'var(--space-2)' }}>Monto</th>
                            <th style={{ padding: 'var(--space-2)' }}>Sync</th>
                        </tr>
                    </thead>
                    <tbody>
                        {propinas.map(p => (
                            <tr key={p.id} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                                <td style={{ padding: 'var(--space-2)' }}>{new Date(p.fecha).toLocaleString()}</td>
                                <td style={{ padding: 'var(--space-2)' }}>{p.fuente}</td>
                                <td style={{ padding: 'var(--space-2)' }}>${p.monto.toFixed(2)}</td>
                                <td style={{ padding: 'var(--space-2)' }}>{p.sincronizada ? '✅' : '⏳'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
