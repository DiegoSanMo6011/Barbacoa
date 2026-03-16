export const sessionIsValid = (token: string | null, expiresAt: string | null): boolean => {
    if (!token || !expiresAt) return false
    const ts = Date.parse(expiresAt)
    if (!Number.isFinite(ts)) return false
    return Date.now() < ts
}

export const getAutoLockMs = (value: string | undefined): number => {
    const minutes = Number(value ?? '10')
    if (!Number.isFinite(minutes) || minutes <= 0) return 0
    return Math.floor(minutes * 60_000)
}
