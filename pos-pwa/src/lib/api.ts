import { useSessionStore } from '../store/sessionStore'

const API_BASE_DEFAULT = '/api'

const trimSlash = (value: string) => value.replace(/\/+$/, '')
const isLocalBrowserHost = (hostname: string) =>
    hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'

export const getApiBase = (): string => {
    if (import.meta.env.PROD) {
        const prodBase = import.meta.env.VITE_API_BASE ?? API_BASE_DEFAULT
        return trimSlash(prodBase)
    }

    const explicit = import.meta.env.VITE_EDGE_URL
    if (explicit && explicit.trim() !== '') {
        // In development, never force localhost API from non-local clients (e.g. phones on LAN).
        // This keeps mobile testing working via Vite proxy (/api).
        const browserHost = typeof window !== 'undefined' ? window.location.hostname : ''
        if (isLocalBrowserHost(browserHost)) {
            return trimSlash(explicit.trim())
        }
    }
    const base = import.meta.env.VITE_API_BASE ?? API_BASE_DEFAULT
    return trimSlash(base)
}

export const apiUrl = (path: string): string => {
    const base = getApiBase()
    if (path.startsWith('http://') || path.startsWith('https://')) return path
    if (!path.startsWith('/')) return `${base}/${path}`
    return `${base}${path}`
}

type ApiFetchOptions = {
    auth?: boolean
    timeoutMs?: number
}

export async function apiFetch(
    path: string,
    init: RequestInit = {},
    options: ApiFetchOptions = {}
): Promise<Response> {
    const { auth = true, timeoutMs = 10_000 } = options
    const headers = new Headers(init.headers ?? {})
    if (auth) {
        const session = useSessionStore.getState()
        if (!session.hasValidSession() || !session.token) {
            throw new Error('Sesión expirada. Vuelve a desbloquear.')
        }
        headers.set('Authorization', `Bearer ${session.token}`)
    }

    const signal = init.signal ?? AbortSignal.timeout(timeoutMs)
    let response: Response
    try {
        response = await fetch(apiUrl(path), {
            ...init,
            headers,
            signal,
        })
    } catch (err: any) {
        const endpoint = apiUrl(path)
        if (err?.name === 'TimeoutError') {
            throw new Error(`Tiempo de espera agotado al conectar con ${endpoint}`)
        }
        throw new Error(
            `Sin conexión con la API (${endpoint}). Revisa red local, certificado TLS y URL de acceso.`
        )
    }
    if (auth && response.status === 401) {
        useSessionStore.getState().clearSession()
    }
    return response
}
