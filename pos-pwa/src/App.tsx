import { useCallback, useEffect, useState } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
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
import Personal from './views/admin/Personal'
import './styles/global.css'
import './styles/components.css'

export default function App() {
    const token = useSessionStore(s => s.token)
    const rol = useSessionStore(s => s.rol)
    const expiresAt = useSessionStore(s => s.expiresAt)
    const clearSession = useSessionStore(s => s.clearSession)
    const isLogged = sessionIsValid(token, expiresAt)
    const [isOnline, setIsOnline] = useState(() =>
        typeof navigator !== 'undefined' ? navigator.onLine : true
    )
    const location = useLocation()
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
        const toOnline = () => setIsOnline(true)
        const toOffline = () => setIsOnline(false)
        window.addEventListener('online', toOnline)
        window.addEventListener('offline', toOffline)

        return () => {
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
            <Route path="/personal" element={rol === 'ADMIN' ? <Personal /> : <Navigate to="/venta" replace />} />
        </Routes>
    )

    return (
        <div className="app-shell">
            <Nav currentPath={location.pathname} onLogout={() => { void logoutEverywhere() }} />
            <main className={`app-main ${location.pathname === '/venta' ? 'app-main--comandas' : ''}`}>
                {routes}
            </main>
        </div>
    )
}
