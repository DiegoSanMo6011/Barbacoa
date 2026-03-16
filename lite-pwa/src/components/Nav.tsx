import { NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useSessionStore } from '../store/sessionStore'

type NavMode = 'mobile' | 'desktop'

type Props = {
    mode?: NavMode
    onLogout?: () => void
}

export default function Nav({ mode = 'mobile', onLogout }: Props) {
    const [isOnline, setIsOnline] = useState(() => navigator.onLine)
    const rol = useSessionStore(s => s.rol)

    const tabs = [
        { to: '/venta', label: 'Cobrar', icon: '🛒' },
        { to: '/corte', label: 'Corte', icon: '🗂️' },
        ...(rol === 'ADMIN' ? [
            { to: '/catalogo', label: 'Catálogo', icon: '📋' },
            { to: '/inventario', label: 'Insumos', icon: '📦' },
            { to: '/gastos', label: 'Gastos', icon: '💸' },
            { to: '/propinas', label: 'Propinas', icon: '💁' },
        ] : []),
    ]

    useEffect(() => {
        const toOnline = () => setIsOnline(true)
        const toOffline = () => setIsOnline(false)
        window.addEventListener('online', toOnline)
        window.addEventListener('offline', toOffline)
        return () => {
            window.removeEventListener('online', toOnline)
            window.removeEventListener('offline', toOffline)
        }
    }, [])

    if (mode === 'desktop') {
        return (
            <aside style={{
                width: 240,
                background: 'var(--color-surface)',
                borderRadius: 'var(--radius-lg)',
                border: '1.5px solid var(--color-border)',
                padding: 'var(--space-4)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-3)',
                height: '100%',
            }}>
                <p style={{
                    fontSize: '0.72rem',
                    color: 'var(--color-text-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    fontWeight: 700,
                }}>
                    Menu principal
                </p>
                {tabs.map(tab => (
                    <NavLink
                        key={tab.to}
                        to={tab.to}
                        style={({ isActive }) => ({
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                            height: 44,
                            borderRadius: 'var(--radius)',
                            padding: '0 var(--space-3)',
                            textDecoration: 'none',
                            fontSize: '0.86rem',
                            fontWeight: 700,
                            color: isActive ? '#fff' : 'var(--color-text-muted)',
                            background: isActive ? 'var(--color-brand)' : 'transparent',
                            border: isActive ? 'none' : '1px solid transparent',
                            transition: 'all var(--transition)',
                        })}
                    >
                        <span style={{ fontSize: '1rem', lineHeight: 1 }}>{tab.icon}</span>
                        {tab.label.toUpperCase()}
                    </NavLink>
                ))}

                <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                    <span className={`connection-badge ${isOnline ? 'online' : 'offline'}`} style={{ width: 'fit-content' }}>
                        {isOnline ? '●' : '○'} {isOnline ? 'Online' : 'Offline'}
                    </span>
                    <button className="btn btn-ghost btn-full" onClick={onLogout}>
                        Cerrar sesion
                    </button>
                </div>
            </aside>
        )
    }

    return (
        <nav style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            height: 88,
            background: 'var(--color-bg)',
            display: 'flex',
            alignItems: 'center',
            padding: '8px 20px 16px 20px',
            zIndex: 130,
        }}>
            <div style={{
                width: '100%',
                height: 62,
                background: 'var(--color-surface)',
                borderRadius: 36,
                border: '1px solid var(--color-border)',
                display: 'flex',
                alignItems: 'center',
                padding: 4,
                gap: 6,
            }}>
                {tabs.map(tab => (
                    <NavLink
                        key={tab.to}
                        to={tab.to}
                        style={({ isActive }) => ({
                            flex: 1,
                            height: 54,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 2,
                            borderRadius: 30,
                            textDecoration: 'none',
                            fontSize: '0.58rem',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                            color: isActive ? '#fff' : 'var(--color-text-muted)',
                            background: isActive ? 'var(--color-brand)' : 'transparent',
                            transition: 'all var(--transition)',
                        })}
                    >
                        <span style={{ fontSize: '1rem', lineHeight: 1 }}>{tab.icon}</span>
                        {tab.label}
                    </NavLink>
                ))}
                <button
                    className="btn btn-ghost btn-icon"
                    title="Cerrar sesión"
                    onClick={onLogout}
                    style={{
                        width: 54,
                        height: 54,
                        minHeight: 54,
                        padding: 0,
                        borderRadius: 30,
                        color: 'var(--color-text-muted)',
                    }}
                >
                    ⎋
                </button>
            </div>
        </nav>
    )
}
