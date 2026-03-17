import { useMemo, useState } from 'react'
import { apiFetch } from '../lib/api'
import { useSessionStore, type UserRole } from '../store/sessionStore'

type UnlockResponse = {
    token: string
    rol: UserRole
    usuario?: string | null
    session_id: string
    expires_at: string
}

const roleOptions: UserRole[] = ['CAJERO', 'ADMIN']

export default function UnlockScreen() {
    const setSession = useSessionStore(s => s.setSession)
    const [rol, setRol] = useState<UserRole>('CAJERO')
    const [usuario, setUsuario] = useState('')
    const [pin, setPin] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const canSubmit = useMemo(() => pin.trim().length >= 4 && !loading, [pin, loading])

    const handleUnlock = async () => {
        if (!canSubmit) return
        setLoading(true)
        setError(null)
        try {
            const res = await apiFetch(
                '/auth/unlock',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pin: pin.trim(), rol, usuario: usuario.trim() || undefined }),
                },
                { auth: false, timeoutMs: 10_000 }
            )

            if (!res.ok) {
                let detail = `HTTP ${res.status}`
                try {
                    const body = await res.json()
                    if (body?.detail) detail = body.detail
                } catch {
                    // ignore parse error
                }
                throw new Error(detail)
            }

            const data: UnlockResponse = await res.json()
            setSession(data)
            setPin('')
        } catch (e: any) {
            setError(e?.message ?? 'No se pudo desbloquear')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={{ minHeight: '100dvh', background: 'var(--color-bg)', display: 'grid', placeItems: 'center', padding: 16 }}>
            <div style={{ width: 'min(100%, 402px)', display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{
                    height: 36,
                    borderRadius: 10,
                    background: 'var(--color-surface)',
                    padding: '10px 12px',
                    color: 'var(--color-text-muted)',
                    fontSize: 11,
                    fontWeight: 500,
                    display: 'flex',
                    alignItems: 'center',
                }}>
                    NUEVO · Sincronizacion protegida incluso sin internet
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <h1 style={{ fontSize: '2rem', lineHeight: 1.18, fontWeight: 700, color: 'var(--color-text)' }}>
                        Cobra rapido.
                        <br />
                        Opera con confianza.
                    </h1>
                    <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                        Acceso simple y seguro para cualquier usuario.
                    </p>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{
                            height: 30,
                            borderRadius: 15,
                            background: 'var(--color-success-bg)',
                            color: 'var(--color-success)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            padding: '0 12px',
                            fontSize: 11,
                            fontWeight: 600,
                        }}>
                            ✓ Sesion auditada
                        </span>
                        <span style={{
                            height: 30,
                            borderRadius: 15,
                            background: 'var(--color-surface-2)',
                            color: 'var(--color-transfer)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            padding: '0 12px',
                            fontSize: 11,
                            fontWeight: 600,
                        }}>
                            🛡️ Auto bloqueo por inactividad
                        </span>
                    </div>
                </div>

                <div style={{
                    borderRadius: 16,
                    background: 'var(--color-surface)',
                    padding: 20,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                }}>
                    <div style={{
                        width: 60,
                        height: 60,
                        borderRadius: 30,
                        background: 'var(--color-brand-bg)',
                        display: 'grid',
                        placeItems: 'center',
                        color: 'var(--color-brand)',
                        fontSize: 26,
                    }}>
                        🔒
                    </div>
                    <h2 style={{ fontSize: 28, lineHeight: 1.05, fontWeight: 700, color: 'var(--color-text)' }}>
                        Ingresa para empezar turno
                    </h2>
                    <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                        Interfaz amigable con bloqueo automatico y registro seguro.
                    </p>

                    <div style={{ height: 40, display: 'flex', gap: 8 }}>
                        {roleOptions.map(option => (
                            <button
                                key={option}
                                className="btn btn-ghost"
                                onClick={() => setRol(option)}
                                disabled={loading}
                                style={{
                                    flex: 1,
                                    height: 40,
                                    minHeight: 40,
                                    border: 'none',
                                    borderRadius: 10,
                                    background: rol === option ? 'var(--color-brand)' : 'var(--color-surface-2)',
                                    color: rol === option ? '#fff' : 'var(--color-text-muted)',
                                    fontSize: 11,
                                    fontWeight: 700,
                                    letterSpacing: '0.05em',
                                }}
                            >
                                {option}
                            </button>
                        ))}
                    </div>

                    <label style={{ fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 600 }}>Usuario</label>
                    <input
                        className="input"
                        type="text"
                        autoComplete="off"
                        placeholder="ej. Ana / Carlos"
                        value={usuario}
                        onChange={e => setUsuario(e.target.value)}
                        maxLength={40}
                        style={{ height: 52, border: 'none', background: 'var(--color-surface-2)', borderRadius: 12 }}
                    />

                    <label style={{ fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 600 }}>PIN</label>
                    <input
                        className="input"
                        type="password"
                        inputMode="numeric"
                        autoComplete="off"
                        placeholder="••••"
                        value={pin}
                        onChange={e => setPin(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === 'Enter') handleUnlock()
                        }}
                        style={{ height: 52, border: 'none', background: 'var(--color-surface-2)', borderRadius: 12 }}
                    />

                    {error && (
                        <div style={{
                            padding: 'var(--space-3)',
                            background: 'var(--color-danger-bg)',
                            color: 'var(--color-danger)',
                            borderRadius: 'var(--radius)',
                            fontWeight: 600,
                            fontSize: '0.82rem',
                        }}>
                            ⚠️ {error}
                        </div>
                    )}

                    <button
                        className="btn btn-primary btn-full btn-lg"
                        style={{ height: 56, borderRadius: 12, marginTop: 2 }}
                        disabled={!canSubmit}
                        onClick={handleUnlock}
                    >
                        {loading ? 'Validando...' : 'Entrar y abrir caja'}
                    </button>

                    <p style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>
                        Si tu sesion expira, vuelve a ingresar PIN.
                    </p>
                </div>

                <div style={{
                    borderRadius: 16,
                    background: 'var(--color-surface)',
                    minHeight: 64,
                    padding: '22px 16px 0 16px',
                    color: 'var(--color-success)',
                    fontSize: 12,
                    fontWeight: 600,
                }}>
                    ✅ Sesion protegida por expiracion e inactividad
                </div>
            </div>
        </div>
    )
}
