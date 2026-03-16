import { useEffect, useState } from 'react'
import { useGastosStore } from '../../store/gastosStore'

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
        <div style={{ padding: 'var(--space-4)', display: 'flex', gap: 'var(--space-4)', width: '100%', height: '100%' }}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <h2>Registrar Gasto</h2>
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    <input
                        className="input"
                        type="number"
                        placeholder="Monto"
                        value={monto}
                        onChange={e => setMonto(e.target.value)}
                        step="0.01"
                        required
                    />
                    <input
                        className="input"
                        placeholder="Concepto (ej. Papel de baño)"
                        value={concepto}
                        onChange={e => setConcepto(e.target.value)}
                        required
                    />
                    <select className="input" value={categoria} onChange={e => setCategoria(e.target.value)}>
                        <option value="OPERATIVO">Operativo</option>
                        <option value="INSUMOS">Insumos extras</option>
                        <option value="MANTENIMIENTO">Mantenimiento</option>
                        <option value="OTRO">Otro</option>
                    </select>
                    <select className="input" value={metodo} onChange={e => setMetodo(e.target.value)}>
                        <option value="EFECTIVO">Efectivo de Caja</option>
                        <option value="TARJETA">Tarjeta</option>
                        <option value="TRANSFER">Transferencia</option>
                    </select>
                    <textarea
                        className="input"
                        placeholder="Notas (opcional)"
                        value={nota}
                        onChange={e => setNota(e.target.value)}
                    />
                    <button className="btn btn-primary" type="submit">Guardar</button>
                </form>
            </div>

            <div style={{ flex: 2, overflowY: 'auto', background: 'var(--color-surface)', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead style={{ background: 'var(--color-bg)', borderBottom: '1px solid var(--color-border)' }}>
                        <tr>
                            <th style={{ padding: 'var(--space-2)' }}>Fecha</th>
                            <th style={{ padding: 'var(--space-2)' }}>Concepto</th>
                            <th style={{ padding: 'var(--space-2)' }}>Categoría</th>
                            <th style={{ padding: 'var(--space-2)' }}>Monto</th>
                            <th style={{ padding: 'var(--space-2)' }}>Método</th>
                            <th style={{ padding: 'var(--space-2)' }}>Sync</th>
                        </tr>
                    </thead>
                    <tbody>
                        {gastos.map(g => (
                            <tr key={g.id} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                                <td style={{ padding: 'var(--space-2)' }}>{new Date(g.fecha).toLocaleString()}</td>
                                <td style={{ padding: 'var(--space-2)' }}>{g.concepto}</td>
                                <td style={{ padding: 'var(--space-2)' }}>{g.categoria}</td>
                                <td style={{ padding: 'var(--space-2)' }}>${g.monto.toFixed(2)}</td>
                                <td style={{ padding: 'var(--space-2)' }}>{g.metodo_pago}</td>
                                <td style={{ padding: 'var(--space-2)' }}>{g.sincronizado ? '✅' : '⏳'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
