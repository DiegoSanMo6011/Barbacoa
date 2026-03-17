import { NavLink } from 'react-router-dom'
import {
    ClipboardList,
    Wallet,
    ReceiptText,
    HandCoins,
    History,
    Package,
    ShoppingCart
} from 'lucide-react'
import { useSessionStore } from '../store/sessionStore'
import './Nav.css'

type Props = {
    currentPath: string
    onLogout?: () => void
}

function iconFor(path: string) {
    if (path === '/venta') return <ShoppingCart size={18} />
    if (path === '/corte') return <ReceiptText size={18} />
    if (path === '/catalogo') return <ClipboardList size={18} />
    if (path === '/inventario') return <Package size={18} />
    if (path === '/gastos') return <Wallet size={18} />
    if (path === '/propinas') return <HandCoins size={18} />
    if (path === '/historial') return <History size={18} />
    return <ClipboardList size={18} />
}

export default function Nav({ currentPath, onLogout }: Props) {
    const rol = useSessionStore((s) => s.rol)

    const routes = [
        { path: '/venta', label: 'Cobrar' },
        { path: '/corte', label: 'Corte' },
        ...(rol === 'ADMIN' ? [
            { path: '/catalogo', label: 'Catálogo' },
            { path: '/inventario', label: 'Insumos' },
            { path: '/gastos', label: 'Gastos' },
            { path: '/propinas', label: 'Propinas' }
        ] : []),
    ]

    const mobilePriority = ['/venta', '/corte', '/gastos']
    const mobileRoutes = mobilePriority
        .map((path) => routes.find((route) => route.path === path))
        .filter(Boolean) as typeof routes

    return (
        <>
            <aside className="app-sidebar">
                <div className="app-sidebar-title">Menu principal</div>
                <div className="app-sidebar-items">
                    {routes.map((route) => (
                        <NavLink
                            key={route.path}
                            to={route.path}
                            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                        >
                            {iconFor(route.path)}
                            <span>{route.label}</span>
                        </NavLink>
                    ))}
                </div>

                <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                    <button className="btn btn-ghost btn-full" onClick={onLogout}>
                        Cerrar sesión
                    </button>
                </div>
            </aside>

            <nav className="app-bottom-nav">
                {mobileRoutes.map((route) => (
                    <NavLink
                        key={route.path}
                        to={route.path}
                        className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
                    >
                        {iconFor(route.path)}
                        <span>{route.label}</span>
                    </NavLink>
                ))}
            </nav>
        </>
    )
}
