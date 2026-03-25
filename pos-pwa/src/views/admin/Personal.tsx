import { useEffect, useState } from 'react'
import { Users, PlusCircle, CheckCircle2, Circle, Loader2 } from 'lucide-react'
import { apiFetch } from '../../lib/api'

type Mesero = {
    id: string
    nombre: string
    activo: boolean
    created_at: string
}

export default function Personal() {
    const [meseros, setMeseros] = useState<Mesero[]>([])
    const [nombre, setNombre] = useState('')
    const [loading, setLoading] = useState(false)
    const [fetching, setFetching] = useState(true)

    const cargarMeseros = async () => {
        try {
            setFetching(true)
            const res = await apiFetch('/meseros')
            if (res.ok) {
                const data = await res.json()
                setMeseros(data)
            }
        } catch (e) {
            console.error('Error al cargar meseros:', e)
        } finally {
            setFetching(false)
        }
    }

    useEffect(() => {
        void cargarMeseros()
    }, [])

    const handleCrear = async (e: React.FormEvent) => {
        e.preventDefault()
        const nom = nombre.trim()
        if (!nom) return
        setLoading(true)
        try {
            const res = await apiFetch('/meseros', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nombre: nom })
            })
            if (res.ok) {
                setNombre('')
                void cargarMeseros()
            } else {
                window.alert('Error al crear mesero')
            }
        } catch (e) {
            console.error(e)
            window.alert('Error de red al crear mesero')
        } finally {
            setLoading(false)
        }
    }

    const toggleActivo = async (id: string, actual: boolean) => {
        const confirmMsg = actual
            ? '¿Estás seguro de desactivar a este mesero? Ya no aparecerá en la lista para asignar comandas.'
            : '¿Deseas reactivar a este mesero?'
        if (!window.confirm(confirmMsg)) return

        try {
            const res = await apiFetch(`/meseros/${id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ activo: !actual })
            })
            if (res.ok) {
                void cargarMeseros()
            }
        } catch (e) {
            console.error(e)
            window.alert('No se pudo cambiar el estado del mesero')
        }
    }

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', padding: 'var(--space-4)', overflowY: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                <Users size={28} style={{ color: 'var(--color-brand)' }} />
                <h2 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0 }}>Gestión de Personal</h2>
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
                        <PlusCircle size={18} /> Registrar Nuevo Mesero
                    </h3>
                    <form onSubmit={handleCrear} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                            Nombre del Mesero
                            <input
                                className="input"
                                type="text"
                                placeholder="Ej. Carlos, Ana..."
                                value={nombre}
                                onChange={e => setNombre(e.target.value)}
                                required
                            />
                        </label>
                        <button className="btn btn-primary" type="submit" disabled={loading} style={{ marginTop: 'var(--space-2)' }}>
                            {loading ? 'Guardando...' : 'Crear Mesero'}
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
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Plantilla Actual</h3>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ minWidth: 600, width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                            <thead style={{ background: 'var(--color-surface)', borderBottom: '2px solid var(--color-border)' }}>
                                <tr>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Nombre</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600 }}>Registro</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600, textAlign: 'center' }}>Estado</th>
                                    <th style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontWeight: 600, textAlign: 'right' }}>Acciones</th>
                                </tr>
                            </thead>
                            <tbody>
                                {fetching && meseros.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-faint)' }}>
                                            <Loader2 size={24} className="spin" style={{ margin: '0 auto', opacity: 0.5 }} />
                                            <div style={{ marginTop: 8 }}>Cargando personal...</div>
                                        </td>
                                    </tr>
                                ) : meseros.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-faint)' }}>
                                            No hay personal registrado en el sistema.
                                        </td>
                                    </tr>
                                ) : (
                                    meseros.map(m => (
                                        <tr key={m.id} style={{ borderBottom: '1px solid var(--color-border-subtle)', opacity: m.activo ? 1 : 0.6 }}>
                                            <td style={{ padding: 'var(--space-3)', fontWeight: 700 }}>
                                                {m.nombre}
                                            </td>
                                            <td style={{ padding: 'var(--space-3)', color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                                                {new Date(m.created_at).toLocaleDateString()}
                                            </td>
                                            <td style={{ padding: 'var(--space-3)', textAlign: 'center' }}>
                                                {m.activo ? (
                                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'var(--color-success-bg)', color: 'var(--color-success)', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem', fontWeight: 700 }}>
                                                        <CheckCircle2 size={12} /> Activo
                                                    </span>
                                                ) : (
                                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'var(--color-surface-2)', color: 'var(--color-text-muted)', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem', fontWeight: 700 }}>
                                                        <Circle size={12} /> Inactivo
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{ padding: 'var(--space-3)', textAlign: 'right' }}>
                                                <button
                                                    className={`btn ${m.activo ? 'btn-danger' : 'btn-primary'}`}
                                                    style={{ height: 32, padding: '0 12px', fontSize: '0.8rem' }}
                                                    onClick={() => toggleActivo(m.id, m.activo)}
                                                >
                                                    {m.activo ? 'Desactivar' : 'Activar'}
                                                </button>
                                            </td>
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
