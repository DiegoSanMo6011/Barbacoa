import { useCallback, useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import VentaRapida from './views/VentaRapida'
import Catalogo from './views/Catalogo'
import Corte from './views/Corte'
import Nav from './components/Nav'
import UnlockScreen from './components/UnlockScreen'
import { useSessionStore } from './store/sessionStore'
import { iniciarSincronizador } from './sync/syncQueue'
import { sincronizarCatalogo } from './sync/catalogoSync'
import { apiFetch } from './lib/api'
import { getAutoLockMs, sessionIsValid } from './lib/session'
import Inventario from './views/admin/Inventario'
import Gastos from './views/admin/Gastos'
import Propinas from './views/admin/Propinas'

export default function App() {
    const token = useSessionStore(s => s.token)
    const rol = useSessionStore(s => s.rol)
    const expiresAt = useSessionStore(s => s.expiresAt)
    const clearSession = useSessionStore(s => s.clearSession)
    const isLogged = sessionIsValid(token, expiresAt)
    const [isMobile, setIsMobile] = useState(() =>
        typeof window !== 'undefined' ? window.matchMedia('(max-width: 900px)').matches : false
    )
    const [isOnline, setIsOnline] = useState(() =>
        typeof navigator !== 'undefined' ? navigator.onLine : true
    )
    const logoutEverywhere = useCallback(async () => {
        try {
            if (sessionIsValid(token, expiresAt)) {
                await apiFetch('/auth/logout', { method: 'POST' }, { auth: true, timeoutMs: 5_000 })
            }
        } catch {
            // Ignore network/API errors on logout and clear local session anyway.
        } finally {
            clearSession()
        }
    }, [token, expiresAt, clearSession])

    useEffect(() => {
        if (!isLogged) return
        sincronizarCatalogo().catch(() => { })
        const stop = iniciarSincronizador()
        return stop
    }, [isLogged])

    useEffect(() => {
        if (!isLogged) return
        const autoLockMs = getAutoLockMs(import.meta.env.VITE_AUTO_LOCK_MINUTES)
        if (autoLockMs <= 0) return

        let timeoutId = window.setTimeout(() => {
            void logoutEverywhere()
        }, autoLockMs)

        const refresh = () => {
            clearTimeout(timeoutId)
            timeoutId = window.setTimeout(() => {
                void logoutEverywhere()
            }, autoLockMs)
        }

        const events: Array<keyof WindowEventMap> = ['pointerdown', 'keydown', 'touchstart', 'mousemove']
        events.forEach(eventName => window.addEventListener(eventName, refresh, { passive: true }))
        document.addEventListener('visibilitychange', refresh)

        return () => {
            clearTimeout(timeoutId)
            events.forEach(eventName => window.removeEventListener(eventName, refresh))
            document.removeEventListener('visibilitychange', refresh)
        }
    }, [isLogged, logoutEverywhere])

    useEffect(() => {
        const mql = window.matchMedia('(max-width: 900px)')
        const onResize = (ev?: MediaQueryListEvent) => setIsMobile(ev?.matches ?? mql.matches)
        onResize()
        if (typeof mql.addEventListener === 'function') {
            mql.addEventListener('change', onResize)
        } else {
            mql.addListener(onResize)
        }

        const toOnline = () => setIsOnline(true)
        const toOffline = () => setIsOnline(false)
        window.addEventListener('online', toOnline)
        window.addEventListener('offline', toOffline)

        return () => {
            if (typeof mql.removeEventListener === 'function') {
                mql.removeEventListener('change', onResize)
            } else {
                mql.removeListener(onResize)
            }
            window.removeEventListener('online', toOnline)
            window.removeEventListener('offline', toOffline)
        }
    }, [])

    if (!isLogged) {
        return <UnlockScreen />
    }

    const routes = (
        <Routes>
            <Route path="/" element={<Navigate to="/venta" replace />} />
            <Route path="/venta" element={<VentaRapida />} />
            <Route path="/corte" element={<Corte />} />
            <Route path="/catalogo" element={rol === 'ADMIN' ? <Catalogo /> : <Navigate to="/venta" replace />} />
            <Route path="/inventario" element={rol === 'ADMIN' ? <Inventario /> : <Navigate to="/venta" replace />} />
            <Route path="/gastos" element={rol === 'ADMIN' ? <Gastos /> : <Navigate to="/venta" replace />} />
            <Route path="/propinas" element={rol === 'ADMIN' ? <Propinas /> : <Navigate to="/venta" replace />} />
        </Routes>
    )

    if (isMobile) {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh', background: 'var(--color-bg)' }}>
                <main style={{ flex: 1, paddingBottom: '88px' }}>
                    {routes}
                </main>
                <Nav mode="mobile" onLogout={() => { void logoutEverywhere() }} />
            </div>
        )
    }

    return (
        <div style={{
            minHeight: '100dvh',
            background: 'var(--color-surface-2)',
            display: 'flex',
            padding: '24px',
            gap: '24px',
        }}>
            <Nav mode="desktop" onLogout={() => { void logoutEverywhere() }} />
            <main style={{
                flex: 1,
                minWidth: 0,
                background: 'var(--color-surface)',
                borderRadius: 'var(--radius-lg)',
                border: '1.5px solid var(--color-border)',
                overflow: 'hidden', // Let the views handle their own scrolling
                display: 'flex',
                flexDirection: 'column',
            }}>
                {routes}
            </main>
        </div>
    )
}
