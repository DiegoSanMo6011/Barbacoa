/**
 * Corte — Jornada de caja diaria
 * Muestra resumen de ventas del día y permite abrir/cerrar jornada
 */
import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/api'

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

const REFRESH_MS = 10_000

type Jornada = {
    id: string
    fecha: string
    status: string
    caja_chica_inicial: number
    total_ventas: number
    total_efectivo: number
    total_tarjeta: number
    total_transfer: number
    efectivo_teorico: number
    efectivo_contado: number | null
    diferencia: number | null
    folio_corte: string | null
    abierto_at: string
    cerrado_at: string | null
}

export default function Corte() {
    const [jornada, setJornada] = useState<Jornada | null>(null)
    const [cargando, setCargando] = useState(true)
    const [cajaChica, setCajaChica] = useState('')
    const [efectivoContado, setEfectivoContado] = useState('')
    const [procesando, setProcesando] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [isMobile, setIsMobile] = useState(() =>
        typeof window !== 'undefined' ? window.matchMedia('(max-width: 900px)').matches : false
    )

    const cargarJornada = async (silencioso = false) => {
        if (!silencioso) setCargando(true)
        try {
            const res = await apiFetch('/corte', {}, { timeoutMs: 6_000 })
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const data = await res.json()
            setJornada(data)
            setError(null)
        } catch (e: any) {
            setError(e.message ?? 'Error desconocido de conexión')
        } finally {
            if (!silencioso) setCargando(false)
        }
    }

    useEffect(() => {
        cargarJornada()
        const id = window.setInterval(() => {
            cargarJornada(true).catch(() => { })
        }, REFRESH_MS)
        return () => clearInterval(id)
    }, [])

    useEffect(() => {
        const mql = window.matchMedia('(max-width: 900px)')
        const onResize = (ev?: MediaQueryListEvent) => setIsMobile(ev?.matches ?? mql.matches)
        onResize()
        if (typeof mql.addEventListener === 'function') {
            mql.addEventListener('change', onResize)
            return () => mql.removeEventListener('change', onResize)
        }
        mql.addListener(onResize)
        return () => mql.removeListener(onResize)
    }, [])

    const handleAbrir = async () => {
        setProcesando(true)
        setError(null)
        try {
            const res = await apiFetch('/corte/abrir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ caja_chica_inicial: parseFloat(cajaChica || '0') }),
            })
            if (!res.ok) throw new Error(await res.text())
            await cargarJornada()
        } catch (e: any) {
            setError(e.message ?? 'Error al abrir jornada')
        } finally {
            setProcesando(false)
        }
    }

    const handleCerrar = async () => {
        if (!efectivoContado) return
        setProcesando(true)
        setError(null)
        try {
            const res = await apiFetch('/corte/cerrar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ efectivo_reportado: parseFloat(efectivoContado) }),
            })
            if (!res.ok) throw new Error(await res.text())
            await cargarJornada()
        } catch (e: any) {
            setError(e.message ?? 'Error al cerrar jornada')
        } finally {
            setProcesando(false)
        }
    }

    const handleReabrir = async () => {
        setProcesando(true)
        setError(null)
        try {
            const res = await apiFetch('/corte/reabrir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            })
            if (!res.ok) throw new Error(await res.text())
            setEfectivoContado('')
            await cargarJornada()
        } catch (e: any) {
            setError(e.message ?? 'Error al reabrir jornada')
        } finally {
            setProcesando(false)
        }
    }

    const efectivoEsperadoEnVivo = jornada
        ? jornada.caja_chica_inicial + jornada.total_efectivo
        : 0

    if (cargando) return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: 'var(--color-text-muted)' }}>
            ⏳ Cargando jornada...
        </div>
    )

    return (
        <div style={{
            width: '100%',
            maxWidth: isMobile ? 560 : 1120,
            margin: '0 auto',
            padding: 'var(--space-5)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-5)',
        }}>

            {/* Header */}
            <div>
                <h1 style={{ fontSize: '1.4rem', fontWeight: 800 }}>🗂️ Corte de Caja</h1>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginTop: 4 }}>
                    {new Date().toLocaleDateString('es-MX', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                </p>
            </div>

            {error && (
                <div style={{ padding: 'var(--space-3) var(--space-4)', background: 'var(--color-danger-bg)', color: 'var(--color-danger)', borderRadius: 'var(--radius)', fontWeight: 600, fontSize: '0.85rem' }}>
                    ⚠️ {error}
                </div>
            )}

            {/* Sin jornada */}
            {!jornada && (
                <div style={{ background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', border: '1.5px solid var(--color-border)', padding: 'var(--space-6)', textAlign: 'center' }}>
                    <p style={{ fontSize: '2.5rem', marginBottom: 'var(--space-4)' }}>☀️</p>
                    <h2 style={{ fontWeight: 700, marginBottom: 'var(--space-2)' }}>No hay jornada abierta</h2>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginBottom: 'var(--space-5)' }}>
                        Define tu fondo de caja e inicia el día
                    </p>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                        <input
                            className="input"
                            type="number"
                            inputMode="decimal"
                            placeholder="Fondo inicial (ej. 500)"
                            value={cajaChica}
                            onChange={e => setCajaChica(e.target.value)}
                        />
                    </div>
                    <button className="btn btn-primary btn-full btn-lg" onClick={handleAbrir} disabled={procesando}>
                        {procesando ? '⏳...' : '☀️ Abrir jornada'}
                    </button>
                </div>
            )}

            {/* Jornada activa o cerrada */}
            {jornada && (
                <>
                    {/* Status badge */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <span style={{
                            padding: '4px 14px',
                            borderRadius: 99,
                            fontWeight: 700,
                            fontSize: '0.8rem',
                            background: jornada.status === 'ABIERTA' ? 'var(--color-success-bg)' : 'var(--color-surface-2)',
                            color: jornada.status === 'ABIERTA' ? 'var(--color-success)' : 'var(--color-text-muted)',
                        }}>
                            {jornada.status === 'ABIERTA' ? '● ABIERTA' : '■ CERRADA'}
                        </span>
                        {jornada.folio_corte && (
                            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                                {jornada.folio_corte}
                            </span>
                        )}
                    </div>

                    {/* Resumen de ventas */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr',
                        gap: 'var(--space-4)',
                    }}>
                        <div style={{ background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', border: '1.5px solid var(--color-border)', overflow: 'hidden' }}>
                            <div style={{ padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                                <p style={{ fontWeight: 700, fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                    Resumen del día
                                </p>
                            </div>

                            {[
                                { label: 'Total ventas', valor: jornada.total_ventas, bold: true },
                                { label: '↳ Efectivo', valor: jornada.total_efectivo, color: 'var(--color-efectivo)' },
                                { label: '↳ Tarjeta', valor: jornada.total_tarjeta, color: 'var(--color-tarjeta)' },
                                { label: '↳ Transferencia', valor: jornada.total_transfer, color: 'var(--color-transfer)' },
                            ].map((row, i) => (
                                <div key={i} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    padding: 'var(--space-3) var(--space-5)',
                                    borderBottom: i === 0 ? '1px solid var(--color-border)' : 'none',
                                }}>
                                    <span style={{ fontSize: row.bold ? '1rem' : '0.85rem', fontWeight: row.bold ? 700 : 400, color: row.color ?? 'var(--color-text)' }}>
                                        {row.label}
                                    </span>
                                    <span style={{ fontWeight: row.bold ? 800 : 600, fontSize: row.bold ? '1.1rem' : '0.9rem', color: row.color ?? 'var(--color-brand)' }}>
                                        {fmtMXN(row.valor)}
                                    </span>
                                </div>
                            ))}
                        </div>

                        {/* Efectivo en caja */}
                        <div style={{ background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', border: '1.5px solid var(--color-border)', overflow: 'hidden' }}>
                            <div style={{ padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                                <p style={{ fontWeight: 700, fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                    Cuadre de efectivo
                                </p>
                                <p style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginTop: 2 }}>
                                    Actualización automática cada {REFRESH_MS / 1000}s
                                </p>
                            </div>
                            {[
                                { label: 'Fondo inicial', valor: jornada.caja_chica_inicial },
                                { label: 'Efectivo esperado', valor: efectivoEsperadoEnVivo },
                                { label: 'Efectivo contado', valor: jornada.efectivo_contado ?? 0 },
                            ].map((row, i) => (
                                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-3) var(--space-5)' }}>
                                    <span style={{ fontSize: '0.85rem' }}>{row.label}</span>
                                    <span style={{ fontWeight: 600 }}>{fmtMXN(row.valor)}</span>
                                </div>
                            ))}
                            {jornada.diferencia !== null && (
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between',
                                    padding: 'var(--space-3) var(--space-5)',
                                    background: Math.abs(jornada.diferencia) <= 1 ? 'var(--color-success-bg)' : 'var(--color-danger-bg)',
                                    fontWeight: 700,
                                }}>
                                    <span>Diferencia</span>
                                    <span style={{ color: Math.abs(jornada.diferencia) <= 1 ? 'var(--color-success)' : 'var(--color-danger)' }}>
                                        {fmtMXN(jornada.diferencia)}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Cerrar jornada */}
                    {jornada.status === 'ABIERTA' && (
                        <div style={{ background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', border: '1.5px solid var(--color-border)', padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                            <p style={{ fontWeight: 700 }}>Cerrar jornada</p>
                            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                                Cuenta el efectivo en caja e ingresa el monto
                            </p>
                            <input
                                className="input"
                                type="number"
                                inputMode="decimal"
                                placeholder="Efectivo contado en caja"
                                value={efectivoContado}
                                onChange={e => setEfectivoContado(e.target.value)}
                                style={{ fontSize: '1.2rem', fontWeight: 700, height: 56 }}
                            />
                            <button
                                className="btn btn-danger btn-full btn-lg"
                                onClick={handleCerrar}
                                disabled={!efectivoContado || procesando}
                            >
                                {procesando ? '⏳...' : '🔒 Cerrar jornada'}
                            </button>
                        </div>
                    )}

                    {jornada.status !== 'ABIERTA' && (
                        <div style={{ background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', border: '1.5px solid var(--color-border)', padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            <p style={{ fontWeight: 700 }}>Reabrir jornada</p>
                            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                                Úsalo solo si cerraste por error y necesitas seguir cobrando.
                            </p>
                            <button
                                className="btn btn-primary btn-full"
                                onClick={handleReabrir}
                                disabled={procesando}
                            >
                                {procesando ? '⏳...' : '🔓 Reabrir caja'}
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}
