/**
 * Catalogo — CRUD básico de productos y modificadores
 * Vista de administración del catálogo (sin stock)
 */
import { useState, useCallback, useMemo, useEffect } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db, CategoriaLocal, ProductoLocal } from '../db/localDB'
import { sincronizarCatalogo } from '../sync/catalogoSync'
import { apiFetch } from '../lib/api'

const fmtMXN = (n: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(n)

type ProductoConCategoria = ProductoLocal & { categoria_nombre: string }
type PersonalizacionTipo = 'NINGUNA' | 'TACO' | 'TORTA'

type NuevoProductoForm = {
    nombre: string
    precio_base: string
    categoria_id: string
    descripcion: string
    personalizacion_tipo: PersonalizacionTipo
}

type PlantillaOpcion = {
    id: number
    nombre: string
    precio_delta: number
    es_default: boolean
    orden: number
}

type PlantillaGrupo = {
    grupo_id: number
    grupo_nombre: string
    obligatorio: boolean
    seleccion_max: number
    orden: number
    opciones: PlantillaOpcion[]
}

type PlantillaOut = {
    tipo: 'TACO' | 'TORTA'
    grupos: PlantillaGrupo[]
}

const formInicial: NuevoProductoForm = {
    nombre: '',
    precio_base: '',
    categoria_id: '',
    descripcion: '',
    personalizacion_tipo: 'NINGUNA',
}

export default function Catalogo() {
    const [sincronizando, setSincronizando] = useState(false)
    const [busqueda, setBusqueda] = useState('')
    const [expandida, setExpandida] = useState<number | null>(null)
    const [mostrarNuevo, setMostrarNuevo] = useState(false)
    const [guardando, setGuardando] = useState(false)
    const [actualizandoId, setActualizandoId] = useState<number | null>(null)
    const [eliminandoId, setEliminandoId] = useState<number | null>(null)
    const [cargandoPlantilla, setCargandoPlantilla] = useState(false)
    const [guardandoPlantilla, setGuardandoPlantilla] = useState(false)
    const [tipoPlantillaActiva, setTipoPlantillaActiva] = useState<PlantillaOut['tipo']>('TACO')
    const [plantillaActiva, setPlantillaActiva] = useState<PlantillaOut | null>(null)
    const [grupoPlantilla, setGrupoPlantilla] = useState('')
    const [nuevaOpcionNombre, setNuevaOpcionNombre] = useState('')
    const [nuevaOpcionCosto, setNuevaOpcionCosto] = useState('')
    const [mensaje, setMensaje] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [formNuevo, setFormNuevo] = useState<NuevoProductoForm>(formInicial)
    const [mostrarPlantillasMobile, setMostrarPlantillasMobile] = useState(false)
    const [isMobile, setIsMobile] = useState(() =>
        typeof window !== 'undefined' ? window.matchMedia('(max-width: 900px)').matches : false
    )

    const categorias = useLiveQuery<CategoriaLocal[]>(() =>
        db.catalogo.orderBy('orden').toArray()
    ) ?? []

    const productosFiltrados = useMemo<ProductoConCategoria[]>(() => {
        return categorias.flatMap(c =>
            c.productos
                .filter(p => busqueda === '' || p.nombre.toLowerCase().includes(busqueda.toLowerCase()))
                .map(p => ({ ...p, categoria_nombre: c.nombre }))
        )
    }, [categorias, busqueda])

    const totalProductos = categorias.reduce((s, c) => s + c.productos.length, 0)

    const handleSincronizar = useCallback(async () => {
        setSincronizando(true)
        setError(null)
        try {
            await sincronizarCatalogo()
        } catch {
            setError('No se pudo sincronizar catálogo')
        } finally {
            setSincronizando(false)
        }
    }, [])

    const cargarPlantillaActiva = useCallback(async () => {
        setCargandoPlantilla(true)
        try {
            const res = await apiFetch(`/productos/plantillas/${tipoPlantillaActiva}`)
            if (!res.ok) throw new Error(await res.text())
            const data: PlantillaOut = await res.json()
            setPlantillaActiva(data)
            setGrupoPlantilla(prev => {
                if (prev && data.grupos.some(g => g.grupo_nombre === prev)) return prev
                return data.grupos[0]?.grupo_nombre || ''
            })
        } catch {
            setError(`No se pudo cargar plantilla ${tipoPlantillaActiva.toLowerCase()}`)
        } finally {
            setCargandoPlantilla(false)
        }
    }, [tipoPlantillaActiva])

    useEffect(() => {
        cargarPlantillaActiva().catch(() => { })
    }, [cargarPlantillaActiva])

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

    const handleCrearProducto = useCallback(async () => {
        setMensaje(null)
        setError(null)

        const nombre = formNuevo.nombre.trim()
        const precioBase = formNuevo.precio_base.trim() === '' ? 0 : parseFloat(formNuevo.precio_base)
        const categoriaId = Number(formNuevo.categoria_id)

        if (!nombre) {
            setError('El nombre del producto es obligatorio')
            return
        }
        if (!Number.isFinite(precioBase) || precioBase < 0) {
            setError('El precio base debe ser un número mayor o igual a 0')
            return
        }
        if (!Number.isFinite(categoriaId) || categoriaId <= 0) {
            setError('Selecciona una categoría')
            return
        }

        setGuardando(true)
        try {
            const res = await apiFetch('/productos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nombre,
                    precio_base: precioBase,
                    categoria_id: categoriaId,
                    descripcion: formNuevo.descripcion.trim() || null,
                    precio_abierto: false,
                    personalizacion_tipo: formNuevo.personalizacion_tipo,
                }),
            })

            if (!res.ok) {
                const detalle = await res.text()
                throw new Error(detalle || 'No se pudo crear el producto')
            }

            await sincronizarCatalogo()
            setFormNuevo(formInicial)
            setMostrarNuevo(false)
            setExpandida(categoriaId)
            setMensaje(`Producto "${nombre}" creado`)
        } catch (e: any) {
            setError(e?.message ?? 'Error al crear producto')
        } finally {
            setGuardando(false)
        }
    }, [formNuevo])

    const handleEditarPersonalizacion = useCallback(async (p: ProductoConCategoria) => {
        if (p.precio_abierto) {
            setError('"Pastel personalizable" es de costo abierto y no acepta plantilla de modificadores')
            return
        }

        const sugerido = p.personalizacion_tipo ?? 'NINGUNA'
        const raw = window.prompt(
            `Plantilla para "${p.nombre}" (NINGUNA | TACO | TORTA)`,
            sugerido
        )
        if (raw === null) return

        const tipo = raw.trim().toUpperCase() as PersonalizacionTipo
        if (!['NINGUNA', 'TACO', 'TORTA'].includes(tipo)) {
            setError('Plantilla inválida. Usa NINGUNA, TACO o TORTA.')
            return
        }

        setActualizandoId(p.id)
        setMensaje(null)
        setError(null)
        try {
            const res = await apiFetch(`/productos/${p.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    personalizacion_tipo: tipo,
                    precio_abierto: false,
                }),
            })

            if (!res.ok) {
                const detalle = await res.text()
                throw new Error(detalle || 'No se pudo actualizar personalización')
            }

            await sincronizarCatalogo()
            setMensaje(`Personalización actualizada para "${p.nombre}"`)
        } catch (e: any) {
            setError(e?.message ?? 'Error al actualizar personalización')
        } finally {
            setActualizandoId(null)
        }
    }, [])

    const handleAgregarOpcionPlantilla = useCallback(async () => {
        const nombre = nuevaOpcionNombre.trim()
        const precio = parseFloat(nuevaOpcionCosto || '0')
        if (!grupoPlantilla) {
            setError('Selecciona un grupo para agregar opción')
            return
        }
        if (!nombre) {
            setError('El nombre de la opción es obligatorio')
            return
        }
        if (!Number.isFinite(precio)) {
            setError('El costo de la opción no es válido')
            return
        }

        setGuardandoPlantilla(true)
        setError(null)
        setMensaje(null)
        try {
            const res = await apiFetch(`/productos/plantillas/${tipoPlantillaActiva}/opciones`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    grupo_nombre: grupoPlantilla,
                    nombre,
                    precio_delta: precio,
                }),
            })
            if (!res.ok) {
                const detalle = await res.text()
                throw new Error(detalle || 'No se pudo agregar opción')
            }

            setNuevaOpcionNombre('')
            setNuevaOpcionCosto('')
            await cargarPlantillaActiva()
            await sincronizarCatalogo()
            setMensaje(`Opción "${nombre}" agregada en ${grupoPlantilla}`)
        } catch (e: any) {
            setError(e?.message ?? 'Error al agregar opción')
        } finally {
            setGuardandoPlantilla(false)
        }
    }, [grupoPlantilla, nuevaOpcionCosto, nuevaOpcionNombre, tipoPlantillaActiva, cargarPlantillaActiva])

    const handleEliminarOpcionPlantilla = useCallback(async (opcionId: number, opcionNombre: string) => {
        const confirmar = window.confirm(`¿Quitar opción "${opcionNombre}" de la plantilla?`)
        if (!confirmar) return

        setGuardandoPlantilla(true)
        setError(null)
        setMensaje(null)
        try {
            const res = await apiFetch(`/productos/plantillas/${tipoPlantillaActiva}/opciones/${opcionId}`, {
                method: 'DELETE',
            })
            if (!res.ok) {
                const detalle = await res.text()
                throw new Error(detalle || 'No se pudo eliminar opción')
            }
            await cargarPlantillaActiva()
            await sincronizarCatalogo()
            setMensaje(`Opción "${opcionNombre}" eliminada`)
        } catch (e: any) {
            setError(e?.message ?? 'Error al eliminar opción')
        } finally {
            setGuardandoPlantilla(false)
        }
    }, [tipoPlantillaActiva, cargarPlantillaActiva])

    const handleEditarCostoOpcionPlantilla = useCallback(async (opcion: PlantillaOpcion) => {
        const raw = window.prompt(`Nuevo costo para "${opcion.nombre}"`, String(opcion.precio_delta))
        if (raw === null) return
        const precio = parseFloat(raw.replace(',', '.'))
        if (!Number.isFinite(precio)) {
            setError('Costo inválido')
            return
        }

        setGuardandoPlantilla(true)
        setError(null)
        setMensaje(null)
        try {
            const res = await apiFetch(`/productos/plantillas/${tipoPlantillaActiva}/opciones/${opcion.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ precio_delta: precio }),
            })
            if (!res.ok) {
                const detalle = await res.text()
                throw new Error(detalle || 'No se pudo actualizar costo')
            }
            await cargarPlantillaActiva()
            await sincronizarCatalogo()
            setMensaje(`Costo actualizado para "${opcion.nombre}"`)
        } catch (e: any) {
            setError(e?.message ?? 'Error al actualizar costo')
        } finally {
            setGuardandoPlantilla(false)
        }
    }, [tipoPlantillaActiva, cargarPlantillaActiva])

    const handleEliminarProducto = useCallback(async (p: ProductoConCategoria) => {
        setMensaje(null)
        setError(null)

        const confirmar = window.confirm(`¿Eliminar "${p.nombre}" del catálogo?`)
        if (!confirmar) return

        setEliminandoId(p.id)
        try {
            const res = await apiFetch(`/productos/${p.id}`, {
                method: 'DELETE',
            })

            if (!res.ok) {
                const detalle = await res.text()
                throw new Error(detalle || 'No se pudo eliminar el producto')
            }

            await sincronizarCatalogo()
            setMensaje(`Producto "${p.nombre}" eliminado`)
        } catch (e: any) {
            setError(e?.message ?? 'Error al eliminar producto')
        } finally {
            setEliminandoId(null)
        }
    }, [])

    const grupoSeleccionadoPlantilla =
        plantillaActiva?.grupos.find(g => g.grupo_nombre === grupoPlantilla)
        ?? plantillaActiva?.grupos[0]
        ?? null

    const headerEl = (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
            <div>
                <h1 style={{ fontSize: '1.4rem', fontWeight: 800 }}>📋 Catálogo</h1>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginTop: 2 }}>
                    {totalProductos} productos en {categorias.length} categorías
                </p>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <button
                    className="btn btn-primary"
                    onClick={() => setMostrarNuevo(v => !v)}
                    style={{ fontSize: '0.85rem' }}
                >
                    {mostrarNuevo ? 'Cancelar' : '+ Nuevo producto'}
                </button>
                <button
                    className="btn btn-ghost"
                    onClick={handleSincronizar}
                    disabled={sincronizando}
                    style={{ fontSize: '0.85rem' }}
                >
                    {sincronizando ? '⏳ Sincronizando...' : '🔄 Sincronizar'}
                </button>
            </div>
        </div>
    )

    const alertasEl = (
        <>
            {mensaje && (
                <div style={{ padding: 'var(--space-3) var(--space-4)', background: 'var(--color-success-bg)', color: 'var(--color-success)', borderRadius: 'var(--radius)', fontWeight: 600, fontSize: '0.85rem', marginBottom: 'var(--space-3)' }}>
                    ✓ {mensaje}
                </div>
            )}
            {error && (
                <div style={{ padding: 'var(--space-3) var(--space-4)', background: 'var(--color-danger-bg)', color: 'var(--color-danger)', borderRadius: 'var(--radius)', fontWeight: 600, fontSize: '0.85rem', marginBottom: 'var(--space-3)' }}>
                    ⚠️ {error}
                </div>
            )}
        </>
    )

    const formNuevoEl = (
        <div style={{ background: 'var(--color-surface)', border: '1.5px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <p style={{ fontWeight: 700 }}>Nuevo producto</p>
            <input
                className="input"
                type="text"
                placeholder="Nombre (ej. Matcha Latte)"
                value={formNuevo.nombre}
                onChange={e => setFormNuevo(v => ({ ...v, nombre: e.target.value }))}
            />
            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 'var(--space-3)' }}>
                <input
                    className="input"
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    placeholder="Precio base"
                    value={formNuevo.precio_base}
                    onChange={e => setFormNuevo(v => ({ ...v, precio_base: e.target.value }))}
                />
                <select
                    className="input"
                    value={formNuevo.categoria_id}
                    onChange={e => setFormNuevo(v => ({ ...v, categoria_id: e.target.value }))}
                >
                    <option value="">Selecciona categoría</option>
                    {categorias.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.nombre}</option>
                    ))}
                </select>
            </div>
            <input
                className="input"
                type="text"
                placeholder="Descripción (opcional)"
                value={formNuevo.descripcion}
                onChange={e => setFormNuevo(v => ({ ...v, descripcion: e.target.value }))}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--space-3)' }}>
                <select
                    className="input"
                    value={formNuevo.personalizacion_tipo}
                    onChange={e => setFormNuevo(v => ({
                        ...v,
                        personalizacion_tipo: e.target.value as PersonalizacionTipo,
                    }))}
                >
                    <option value="NINGUNA">Sin personalización</option>
                    <option value="TACO">Plantilla taco</option>
                    <option value="TORTA">Plantilla torta</option>
                </select>
            </div>
            <button className="btn btn-primary btn-full" disabled={guardando} onClick={handleCrearProducto}>
                {guardando ? '⏳ Guardando...' : 'Guardar producto'}
            </button>
        </div>
    )

    const plantillasEl = (
        <div style={{ background: 'var(--color-surface)', border: '1.5px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                <p style={{ fontWeight: 700 }}>
                    Plantilla {tipoPlantillaActiva === 'TACO' ? 'de tacos' : 'de tortas'}
                </p>
                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <button
                        className="btn btn-ghost"
                        style={{
                            fontSize: '0.78rem',
                            background: tipoPlantillaActiva === 'TACO' ? 'var(--color-brand-bg)' : undefined,
                            color: tipoPlantillaActiva === 'TACO' ? 'var(--color-brand)' : undefined,
                        }}
                        onClick={() => setTipoPlantillaActiva('TACO')}
                        disabled={cargandoPlantilla}
                    >
                        TACO
                    </button>
                    <button
                        className="btn btn-ghost"
                        style={{
                            fontSize: '0.78rem',
                            background: tipoPlantillaActiva === 'TORTA' ? 'var(--color-brand-bg)' : undefined,
                            color: tipoPlantillaActiva === 'TORTA' ? 'var(--color-brand)' : undefined,
                        }}
                        onClick={() => setTipoPlantillaActiva('TORTA')}
                        disabled={cargandoPlantilla}
                    >
                        TORTA
                    </button>
                    <button
                        className="btn btn-ghost"
                        onClick={() => cargarPlantillaActiva()}
                        disabled={cargandoPlantilla}
                        style={{ fontSize: '0.8rem' }}
                    >
                        {cargandoPlantilla ? '⏳...' : '↻ Recargar'}
                    </button>
                </div>
            </div>

            {!plantillaActiva && (
                <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                    Cargando plantilla...
                </p>
            )}

            {plantillaActiva && (
                <>
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr 1fr auto',
                        gap: 'var(--space-2)',
                    }}>
                        <select
                            className="input"
                            value={grupoPlantilla}
                            onChange={e => setGrupoPlantilla(e.target.value)}
                        >
                            {plantillaActiva.grupos.map(g => (
                                <option key={g.grupo_id} value={g.grupo_nombre}>{g.grupo_nombre}</option>
                            ))}
                        </select>
                        <input
                            className="input"
                            type="text"
                            placeholder="Nueva opción"
                            value={nuevaOpcionNombre}
                            onChange={e => setNuevaOpcionNombre(e.target.value)}
                        />
                        <input
                            className="input"
                            type="number"
                            inputMode="decimal"
                            step="0.01"
                            placeholder="Costo (+/-)"
                            value={nuevaOpcionCosto}
                            onChange={e => setNuevaOpcionCosto(e.target.value)}
                        />
                        <button
                            className="btn btn-primary"
                            onClick={handleAgregarOpcionPlantilla}
                            disabled={guardandoPlantilla}
                            style={{ whiteSpace: 'nowrap' }}
                        >
                            + Agregar
                        </button>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        {(grupoSeleccionadoPlantilla?.opciones ?? []).map(op => (
                            <div key={op.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--color-surface-2)', borderRadius: 'var(--radius)', padding: 'var(--space-2) var(--space-3)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                                    <span style={{ fontWeight: 600, fontSize: '0.86rem' }}>{op.nombre}</span>
                                    {op.es_default && (
                                        <span style={{ fontSize: '0.68rem', background: 'var(--color-brand-bg)', color: 'var(--color-brand)', borderRadius: 99, padding: '1px 8px', fontWeight: 700 }}>
                                            DEFAULT
                                        </span>
                                    )}
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                                    <span style={{ fontWeight: 700, color: 'var(--color-brand)', minWidth: 72, textAlign: 'right' }}>
                                        {op.precio_delta >= 0 ? '+' : ''}{fmtMXN(op.precio_delta)}
                                    </span>
                                    <button
                                        className="btn btn-ghost btn-icon"
                                        disabled={guardandoPlantilla}
                                        onClick={() => handleEditarCostoOpcionPlantilla(op)}
                                        title="Editar costo"
                                    >
                                        💲
                                    </button>
                                    <button
                                        className="btn btn-ghost btn-icon"
                                        disabled={guardandoPlantilla}
                                        onClick={() => handleEliminarOpcionPlantilla(op.id, op.nombre)}
                                        title="Quitar opción"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>
                        ))}
                        {(grupoSeleccionadoPlantilla?.opciones ?? []).length === 0 && (
                            <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                                Este grupo no tiene opciones activas
                            </p>
                        )}
                    </div>
                </>
            )}
        </div>
    )

    const buscadorEl = (
        <input
            className="input"
            type="search"
            placeholder="🔍 Buscar producto en el catálogo..."
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
        />
    )

    const sinProductosEl = categorias.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--color-text-muted)' }}>
            <p style={{ fontSize: '2.5rem', marginBottom: 'var(--space-4)' }}>📋</p>
            <p style={{ fontWeight: 600 }}>Sin catálogo cargado</p>
            <p style={{ fontSize: '0.85rem', marginTop: 'var(--space-2)', marginBottom: 'var(--space-5)' }}>
                Necesitas conexión al Edge Server para sincronizar
            </p>
            <button className="btn btn-primary" onClick={handleSincronizar} disabled={sincronizando}>
                {sincronizando ? '⏳...' : '🔄 Sincronizar ahora'}
            </button>
        </div>
    ) : null

    const listaEl = (
        <>
            {sinProductosEl}
            {busqueda && productosFiltrados.map(p => (
                <div key={p.id} style={{ background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', border: '1.5px solid var(--color-border)', marginBottom: 'var(--space-2)' }}>
                    <ProductoRow
                        p={p}
                        mostrarCategoria
                        actualizando={actualizandoId === p.id}
                        eliminando={eliminandoId === p.id}
                        onEditarPersonalizacion={handleEditarPersonalizacion}
                        onEliminar={handleEliminarProducto}
                    />
                </div>
            ))}
            {!busqueda && categorias.map(cat => (
                <div key={cat.id} style={{
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1.5px solid var(--color-border)',
                    overflow: 'hidden',
                    marginBottom: 'var(--space-4)',
                }}>
                    <button
                        onClick={() => setExpandida(expandida === cat.id ? null : cat.id)}
                        style={{
                            width: '100%',
                            padding: 'var(--space-4) var(--space-5)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            background: expandida === cat.id ? 'var(--color-brand-bg)' : 'var(--color-surface-2)',
                            borderBottom: expandida === cat.id ? '1px solid var(--color-border)' : 'none',
                            transition: 'background var(--transition)',
                        }}
                    >
                        <div>
                            <span style={{ fontWeight: 700 }}>{cat.nombre}</span>
                            <span style={{ marginLeft: 8, fontSize: '0.78rem', color: 'var(--color-text-muted)', fontWeight: 400 }}>
                                {cat.productos.length} productos
                            </span>
                        </div>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '1.1rem' }}>
                            {expandida === cat.id ? '▲' : '▼'}
                        </span>
                    </button>

                    {expandida === cat.id && cat.productos.map((p, i) => (
                        <div key={p.id} style={{ borderTop: i === 0 ? 'none' : '1px solid var(--color-border)' }}>
                            <ProductoRow
                                p={{ ...p, categoria_nombre: cat.nombre }}
                                actualizando={actualizandoId === p.id}
                                eliminando={eliminandoId === p.id}
                                onEditarPersonalizacion={handleEditarPersonalizacion}
                                onEliminar={handleEliminarProducto}
                            />
                        </div>
                    ))}
                </div>
            ))}
        </>
    )

    if (isMobile) {
        return (
            <div style={{
                minHeight: 'calc(100dvh - 88px)',
                background: 'var(--color-bg)',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
            }}>
                {/* Mobile Compact Header */}
                <div style={{
                    padding: 'var(--space-3) var(--space-4)',
                    background: 'var(--color-surface)',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexShrink: 0,
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <span style={{ fontSize: '1.2rem', fontWeight: 800 }}>📋 Catálogo</span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', background: 'var(--color-surface-2)', padding: '2px 8px', borderRadius: 99, fontWeight: 700 }}>
                            {totalProductos}
                        </span>
                    </div>
                    <button
                        className="btn btn-ghost"
                        onClick={handleSincronizar}
                        disabled={sincronizando}
                        style={{ padding: '6px 10px', fontSize: '0.9rem' }}
                    >
                        {sincronizando ? '⏳' : '🔄 Sync'}
                    </button>
                </div>

                {alertasEl && <div style={{ padding: 'var(--space-3) var(--space-4)' }}>{alertasEl}</div>}

                {/* Buscador Fijo */}
                <div style={{
                    padding: 'var(--space-2) var(--space-4)',
                    background: 'var(--color-surface)',
                    borderBottom: '1px solid var(--color-border)',
                    flexShrink: 0,
                }}>
                    {buscadorEl}
                </div>

                {/* Catálogo de Productos */}
                <div style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: 'var(--space-4)',
                    paddingBottom: '120px', // padding para los FABs
                }}>
                    {listaEl}
                </div>

                {/* Floating Action Buttons */}
                <div style={{
                    position: 'absolute',
                    bottom: 'var(--space-4)',
                    right: 'var(--space-4)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-3)',
                    alignItems: 'flex-end',
                    pointerEvents: 'none',
                }}>
                    <button
                        className="shadow-sm"
                        style={{
                            width: 44, height: 44, borderRadius: 22,
                            fontSize: '1.2rem', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            pointerEvents: 'auto', border: '1px solid var(--color-border)',
                            background: 'var(--color-surface)', color: 'var(--color-text)'
                        }}
                        onClick={() => {
                            setMostrarPlantillasMobile(true)
                            setMostrarNuevo(false)
                        }}
                        title="Plantillas"
                    >
                        ⚙️
                    </button>
                    <button
                        className="btn btn-primary shadow-lg"
                        style={{
                            width: 56, height: 56, borderRadius: 28,
                            fontSize: '1.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            pointerEvents: 'auto', boxShadow: '0 8px 24px rgba(0,0,0,0.2)'
                        }}
                        onClick={() => {
                            setMostrarNuevo(true)
                            setMostrarPlantillasMobile(false)
                        }}
                    >
                        +
                    </button>
                </div>

                {/* Modals for Mobile */}
                {(mostrarNuevo || mostrarPlantillasMobile) && (
                    <div className="modal-overlay" style={{ zIndex: 100 }} onClick={(e) => {
                        if (e.target === e.currentTarget) {
                            setMostrarNuevo(false)
                            setMostrarPlantillasMobile(false)
                        }
                    }}>
                        <div className="modal-card" style={{ maxHeight: '90dvh', width: '100%', margin: 0, borderRadius: '24px 24px 0 0', position: 'absolute', bottom: 0, display: 'flex', flexDirection: 'column' }}>
                            <div style={{ padding: 'var(--space-4)', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontWeight: 800, fontSize: '1.1rem' }}>
                                    {mostrarNuevo ? 'Nuevo Producto' : 'Plantillas y Modificadores'}
                                </span>
                                <button className="btn btn-ghost btn-icon" onClick={() => {
                                    setMostrarNuevo(false)
                                    setMostrarPlantillasMobile(false)
                                }}>✕</button>
                            </div>
                            <div style={{ padding: 'var(--space-4)', overflowY: 'auto' }}>
                                {mostrarNuevo ? formNuevoEl : plantillasEl}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        )
    }

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'row' }}>
            <section style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                minWidth: 0,
            }}>
                <div style={{ padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--color-border)' }}>
                    {headerEl}
                </div>
                {alertasEl}
                <div style={{ padding: 'var(--space-3) var(--space-5)', borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                    {buscadorEl}
                </div>
                <div style={{ flex: 1, padding: 'var(--space-5)', overflow: 'auto', background: 'var(--color-surface-2)' }}>
                    {listaEl}
                </div>
            </section>

            <aside style={{
                width: 440,
                borderLeft: '1.5px solid var(--color-border)',
                background: 'var(--color-surface-2)',
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
            }}>
                <div style={{
                    padding: 'var(--space-4) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    background: 'var(--color-surface)',
                    fontWeight: 700,
                    fontSize: '1.05rem',
                }}>
                    ⚙️ Configuración & Plantillas
                </div>
                <div style={{
                    flex: 1,
                    overflow: 'auto',
                    padding: 'var(--space-5)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-5)',
                }}>
                    {mostrarNuevo && formNuevoEl}
                    {plantillasEl}
                </div>
            </aside>
        </div>
    )
}

function ProductoRow({
    p,
    mostrarCategoria = false,
    actualizando = false,
    eliminando = false,
    onEditarPersonalizacion,
    onEliminar,
}: {
    p: ProductoConCategoria
    mostrarCategoria?: boolean
    actualizando?: boolean
    eliminando?: boolean
    onEditarPersonalizacion?: (producto: ProductoConCategoria) => void
    onEliminar?: (producto: ProductoConCategoria) => void
}) {
    const [expandido, setExpandido] = useState(false)

    return (
        <div
            style={{ padding: 'var(--space-3) var(--space-5)', cursor: p.modificadores.length > 0 ? 'pointer' : 'default' }}
            onClick={() => p.modificadores.length > 0 && setExpandido(x => !x)}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-3)' }}>
                <div>
                    <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{p.nombre}</span>
                    {mostrarCategoria && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>{p.categoria_nombre}</div>
                    )}
                    {p.modificadores.length > 0 && (
                        <span style={{
                            marginLeft: mostrarCategoria ? 0 : 8,
                            fontSize: '0.7rem',
                            background: 'var(--color-brand-bg)',
                            color: 'var(--color-brand)',
                            padding: '1px 7px',
                            borderRadius: 99,
                            fontWeight: 600,
                            display: 'inline-block',
                            marginTop: 4,
                        }}>
                            {p.modificadores.length} grupos
                        </span>
                    )}
                    {p.personalizacion_tipo !== 'NINGUNA' && (
                        <span style={{
                            marginLeft: mostrarCategoria ? 0 : 8,
                            fontSize: '0.7rem',
                            background: 'var(--color-surface-2)',
                            color: 'var(--color-text-muted)',
                            padding: '1px 7px',
                            borderRadius: 99,
                            fontWeight: 700,
                            display: 'inline-block',
                            marginTop: 4,
                        }}>
                            {p.personalizacion_tipo}
                        </span>
                    )}
                    {p.precio_abierto && (
                        <span style={{
                            marginLeft: 6,
                            fontSize: '0.7rem',
                            background: 'var(--color-warning-bg)',
                            color: 'var(--color-warning)',
                            padding: '1px 7px',
                            borderRadius: 99,
                            fontWeight: 700,
                            display: 'inline-block',
                            marginTop: 4,
                        }}>
                            COSTO ABIERTO
                        </span>
                    )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span style={{ fontWeight: 700, color: 'var(--color-brand)', whiteSpace: 'nowrap' }}>
                        {p.precio_abierto ? 'Abierto' : fmtMXN(p.precio_base)}
                    </span>
                    {onEditarPersonalizacion && (
                        <button
                            className="btn btn-ghost btn-icon"
                            disabled={actualizando}
                            onClick={e => {
                                e.preventDefault()
                                e.stopPropagation()
                                onEditarPersonalizacion(p)
                            }}
                            title="Editar plantilla"
                        >
                            {actualizando ? '⏳' : '⚙️'}
                        </button>
                    )}
                    {onEliminar && (
                        <button
                            className="btn btn-ghost btn-icon"
                            disabled={eliminando}
                            onClick={e => {
                                e.preventDefault()
                                e.stopPropagation()
                                onEliminar(p)
                            }}
                            title="Eliminar producto"
                        >
                            {eliminando ? '⏳' : '🗑️'}
                        </button>
                    )}
                </div>
            </div>

            {/* Modificadores expandibles */}
            {expandido && p.modificadores.map(g => (
                <div key={g.grupo_id} style={{
                    marginTop: 'var(--space-2)',
                    padding: 'var(--space-2) var(--space-3)',
                    background: 'var(--color-surface-2)',
                    borderRadius: 'var(--radius)',
                }}>
                    <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-text-muted)', marginBottom: 4 }}>
                        {g.grupo_nombre}{g.obligatorio ? ' *' : ''}
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {g.opciones.map(o => (
                            <span key={o.id} style={{
                                fontSize: '0.75rem',
                                padding: '2px 8px',
                                borderRadius: 99,
                                background: o.es_default ? 'var(--color-brand)' : 'var(--color-border)',
                                color: o.es_default ? '#fff' : 'var(--color-text)',
                            }}>
                                {o.nombre}{o.precio_delta > 0 ? ` +${fmtMXN(o.precio_delta)}` : ''}
                            </span>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    )
}
