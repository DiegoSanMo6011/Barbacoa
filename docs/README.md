# Barbacoa POS 🍖

Sistema de Punto de Venta (POS) para el restaurante **Miranda Barbacoa**, desarrollado en Python con interfaz gráfica (Tkinter/CustomTkinter) y backend en Supabase.

Este proyecto está diseñado para ejecutarse en una Raspberry Pi como sistema principal del restaurante, con soporte para:
- Registro de comandas
- Métodos de pago y cambio
- Gastos y propinas
- Cierre de caja
- Sincronización con Supabase
- Autoinicio al prender la Raspberry Pi

---

## 1) Requisitos

### Software
- Python 3.10+
- Git
- Linux / Raspberry Pi OS
- Entorno gráfico (GUI) activo

### Dependencias del sistema (Linux / Raspberry)
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk git
```

---

## 2) Clonar el repositorio

```bash
git clone git@github.com:DiegoSanMo6011/Barbacoa.git barbacoa_pos
cd barbacoa_pos
```

---

## 3) Crear entorno virtual e instalar dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4) Configurar variables de entorno (Supabase)

Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

Edita `.env`:

```bash
nano .env
```

Ejemplo:

```
SUPABASE_URL=https://TU_PROYECTO.supabase.co
SUPABASE_KEY=TU_ANON_KEY
```

⚠️ **Nunca subas el archivo `.env` a GitHub.**

---

## 5) Ejecutar el sistema manualmente

```bash
source .venv/bin/activate
python app/main.py
```

---

## 6) Autoinicio en Raspberry Pi (modo restaurante)

### Script de arranque

Archivo: `scripts/run_pos.sh`

```bash
#!/usr/bin/env bash

LOG="/home/adminbbq/barbacoa_pos/pos_autostart.log"

echo "=== POS autostart $(date) ===" >> "$LOG"

cd /home/adminbbq/barbacoa_pos
source .venv/bin/activate
python app/main.py >> "$LOG" 2>&1
```

Dar permisos:

```bash
chmod +x scripts/run_pos.sh
```

### Autostart del escritorio

Archivo:

```bash
~/.config/autostart/barbacoa-pos.desktop
```

Contenido:

```
[Desktop Entry]
Type=Application
Name=Barbacoa POS
Exec=/home/adminbbq/barbacoa_pos/scripts/run_pos.sh
Terminal=false
X-GNOME-Autostart-enabled=true
```

---

## 7) Logs del sistema

Para ver errores o ejecución automática:

```bash
cat ~/barbacoa_pos/pos_autostart.log
```

---

## 7.1) Impresora térmica (ESC/POS) vía CUPS

Configuración recomendada para impresora USB (ej. POS-58 / YICHIP3121):

1) Instalar CUPS y permisos:
```bash
sudo apt-get update
sudo apt-get install -y cups
sudo usermod -aG lpadmin adminbbq
sudo usermod -aG lp adminbbq
sudo systemctl enable --now cups
```

2) Abrir CUPS en el navegador:
```
http://localhost:631
```

3) Agregar impresora:
- **Administration → Add Printer**
- Selecciona el dispositivo USB o usa el URI de `lpinfo -v`.
- **Make:** Generic
- **Model:** Generic Text-Only Printer (en)
- Anota el nombre (ej. `velazquez`)

4) Configurar `.env`:
```env
BARBACOA_PRINTER_USE_CUPS=true
BARBACOA_PRINTER_NAME=velazquez
BARBACOA_PRINTER_AUTOPRINT=true
```

5) Probar impresión manual desde el ticket. Si funciona, deja autoprint activado.

## 7.2) Nota sobre estabilidad gráfica (Raspberry)

Para mayor estabilidad con Tkinter, usa **sesión X11** (no Wayland).
- En el login, selecciona “Raspberry Pi OS (X11)”.

---

## 8) Estructura del proyecto

```
barbacoa_pos/
│
├── app/
│   ├── main.py           # App principal POS
│   ├── services/          # Supabase y configuración
│   ├── ui/                # Interfaz gráfica
│
├── scripts/
│   └── run_pos.sh         # Autostart Raspberry
│
├── docs/
│   └── RASPI_SETUP.md     # Guía avanzada Raspberry
│
├── sql/
│   └── schema.sql         # Base de datos Supabase
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## 9) Roadmap del sistema

Funcionalidades actuales:
- POS básico (comandas + pagos)
- Conexión Supabase
- Autoinicio Raspberry
- Impresión de tickets (USB / ESC-POS)
- Roles en app: `MESERO` (default), `GERENTE`, `DUENIO`
- `GERENTE` sin acceso a Reportes (solo dueño)
- Desbloqueo por `ROL + PIN` con caché offline temporal
- Gestión de credenciales por rol (solo dueño)
- Corte con `caja_chica_inicial` para cálculo exacto del efectivo esperado
- Jornada de caja con estados `ABIERTO` / `CERRADO`
- Reapertura de jornada cerrada solo para dueño con confirmación de PIN
- Cambio de PIN disponible para el perfil autenticado (`GERENTE`/`DUENIO`)

### Migración de jornada de caja

Ejecutar en Supabase:

```sql
-- sql/cierres_jornada.sql
```

Incluye:
- `caja_chica_inicial`
- estado de jornada (`ABIERTO`/`CERRADO`)
- metadatos de apertura/cierre/reaperturas
- índice único por `fecha` para evitar duplicados

Próximas mejoras:
- Dashboard de análisis de datos
- Auditoría y trazabilidad por usuario
- Endurecer permisos con RLS en Supabase

### Seed de credenciales por rol

Agregar en `.env`:

```env
BARBACOA_GERENTE_PIN=1234
BARBACOA_DUENIO_PIN=5678
BARBACOA_AUTH_CACHE_TTL_HOURS=24
```

Ejecutar:

```bash
python scripts/seed_roles.py
```

Este script es idempotente y migra registros legacy `ADMIN` a `DUENIO`.

---

## 10) Equipo

Proyecto desarrollado por:
- Gerardo Sánchez (arquitectura + backend + Raspberry)
- CrazyHand (UI / UX / features POS)
- ArturoProgamer777 (datos, lógica de negocio, mejoras)

---

## 11) Filosofía del proyecto

Este POS no es solo un sistema de ventas, sino una plataforma de datos para optimizar el negocio de barbacoa.

Objetivo:
> Convertir la operación del restaurante en datos medibles y decisiones inteligentes.

---
