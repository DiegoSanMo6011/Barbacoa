import { create } from 'zustand'

export type UserRole = 'CAJERO' | 'ADMIN'

type SessionState = {
    token: string | null
    rol: UserRole | null
    usuario: string | null
    sessionId: string | null
    expiresAt: string | null
    setSession: (payload: { token: string; rol: UserRole; usuario?: string | null; session_id: string; expires_at: string }) => void
    clearSession: () => void
    hasValidSession: () => boolean
}

type StoredSession = {
    token: string | null
    rol: UserRole | null
    usuario: string | null
    sessionId: string | null
    expiresAt: string | null
}

const STORAGE_KEY = 'autonoma_pos_session'

const readStoredSession = (): StoredSession => {
    try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) return { token: null, rol: null, usuario: null, sessionId: null, expiresAt: null }
        const parsed = JSON.parse(raw)
        return {
            token: parsed?.token ?? null,
            rol: parsed?.rol ?? null,
            usuario: parsed?.usuario ?? null,
            sessionId: parsed?.sessionId ?? null,
            expiresAt: parsed?.expiresAt ?? null,
        }
    } catch {
        return { token: null, rol: null, usuario: null, sessionId: null, expiresAt: null }
    }
}

const persist = (session: StoredSession) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

const isExpired = (expiresAt: string | null): boolean => {
    if (!expiresAt) return true
    const ts = Date.parse(expiresAt)
    if (!Number.isFinite(ts)) return true
    return Date.now() >= ts
}

const initial = readStoredSession()

export const useSessionStore = create<SessionState>((set, get) => ({
    token: initial.token,
    rol: initial.rol,
    usuario: initial.usuario,
    sessionId: initial.sessionId,
    expiresAt: initial.expiresAt,

    setSession: ({ token, rol, usuario, session_id, expires_at }) => {
        const next = { token, rol, usuario: usuario ?? null, sessionId: session_id, expiresAt: expires_at }
        persist(next)
        set(next)
    },

    clearSession: () => {
        persist({ token: null, rol: null, usuario: null, sessionId: null, expiresAt: null })
        set({ token: null, rol: null, usuario: null, sessionId: null, expiresAt: null })
    },

    hasValidSession: () => {
        const { token, expiresAt } = get()
        return Boolean(token) && !isExpired(expiresAt)
    },
}))
