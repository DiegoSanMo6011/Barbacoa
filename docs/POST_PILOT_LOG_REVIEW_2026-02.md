# Revision tecnica de logs y analisis post-piloto (POS)

## Resumen ejecutivo
- Estado final del piloto: **estable** tras ajustes de sesion grafica e impresion.
- Incidentes criticos encontrados: 2 (crash de sesion grafica, inestabilidad USB de impresora).
- Causa raiz principal: ejecucion de Tkinter sobre **Wayland/Xwayland** en Raspberry Pi OS.
- Mitigacion efectiva: forzar sesion **X11** + configurar impresion por **CUPS**.

## Alcance de revision
- Periodo analizado: Febrero 2026 (piloto en sitio).
- Fuentes:
  - `~/pos_debug.log`
  - `~/barbacoa_pos/app/data/logs/pos.log`
  - `~/.xsession-errors`
  - `dmesg`
  - `journalctl -b -p err --no-pager`

## Hallazgos

### 1) Cierre abrupto de interfaz grafica (Critico)
- Sintoma observado: cierre del POS durante guardado de comanda.
- Evidencia:
  - `X connection to :0 broken (explicit kill or server shutdown).`
  - `failed to read Wayland events: Broken pipe`
  - errores repetidos `xwayland/xwm.c` en `~/.xsession-errors`.
- Impacto: interrupcion de operacion de caja.
- Clasificacion: **Critico**.

### 2) Errores USB de impresora termica (Alto)
- Sintoma observado: impresiones inconsistentes y eventos de reconexion.
- Evidencia:
  - `usb 3-1: device descriptor read/64, error -71` en `dmesg`.
  - deteccion de impresora POS-58 / YICHIP3121.
- Impacto: riesgo de falla de impresion y potencial degradacion de estabilidad.
- Clasificacion: **Alto**.

### 3) Sin evidencia de throttling energetico (Informativo)
- Evidencia:
  - `vcgencmd get_throttled -> throttled=0x0`.
- Interpretacion: no hubo indicios de bajo voltaje durante la ventana analizada.
- Clasificacion: **Informativo**.

## Causa raiz y factores contribuyentes
- Causa raiz principal: incompatibilidad/fragilidad de Xwayland para este flujo UI (Tkinter + dialogs/toplevels) en sesion Wayland (`rpd-labwc`).
- Factor contribuyente: impresion USB en modo crudo con errores `-71` en bus USB.

## Acciones correctivas aplicadas
1. Cambio de sesion a **Raspberry Pi OS (X11)**.
2. Configuracion de impresora via **CUPS** (cola `velazquez`).
3. Driver CUPS seleccionado: **Generic Text-Only Printer (en)**.
4. Pruebas progresivas con flags de ticket/impresion:
   - `BARBACOA_TICKET_PREVIEW`
   - `BARBACOA_TICKET_SAVE`
   - `BARBACOA_PRINTER_AUTOPRINT`
5. Verificacion final con impresion manual y autoprint sin crash.

## Configuracion operativa validada
```env
BARBACOA_PRINTER_USE_CUPS=true
BARBACOA_PRINTER_NAME=velazquez
BARBACOA_PRINTER_AUTOPRINT=true
BARBACOA_TICKET_PREVIEW=true
BARBACOA_TICKET_SAVE=true
```

## Resultado post-mitigacion
- Guardado de comanda: **OK** sin cierre inesperado.
- Vista previa de ticket: **OK**.
- Impresion manual: **OK**.
- Impresion automatica: **OK**.
- Modulo de corte:
  - UX para iniciar/cerrar dia mejorada.
  - Impresion de corte con vista previa: **OK**.

## Riesgos residuales y seguimiento
- Riesgo residual: errores USB intermitentes (`error -71`) pueden reaparecer por cableado/puerto/hub.
- Recomendaciones:
  1. usar cable USB corto y de buena calidad;
  2. preferir hub USB alimentado para impresora termica;
  3. monitorear `dmesg` por 7 dias y registrar incidentes.

## Criterio de cierre de tarea
- Se considera cerrada cuando:
  1. no hay crash durante 3 jornadas consecutivas;
  2. impresion de ticket y corte funciona en 100% de pruebas de cierre;
  3. no aparecen nuevos `Broken pipe` de Xwayland (en sesion X11 no deberian aparecer).
