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

Próximas mejoras:
- Registro de propinas por mesero
- Gestión de gastos
- Pantalla de cierre de caja
- Dashboard de análisis de datos
- Roles (mesero / admin)
- Impresión de tickets

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
