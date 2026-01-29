
# Barbacoa POS System 🍖

Sistema de Punto de Venta (POS) diseñado para la digitalización de comandas, control de gastos, propinas y cierre de caja en restaurantes de barbacoa.

El objetivo del proyecto es construir un sistema funcional, escalable y listo para operación real en hardware de bajo costo (Raspberry Pi), con backend en Supabase.

---

## 🧠 Visión del sistema

Este POS busca cubrir las necesidades reales del negocio:

- Registro digital de comandas.
- Control de ventas por método de pago.
- Registro de gastos operativos.
- Control de propinas por mesero.
- Cierre de caja diario.
- Reportes y análisis de datos.
- Arquitectura preparada para escalabilidad.

---

## 🏗️ Arquitectura general

**Frontend (local):**
- Python + Tkinter/ttk (UI)
- Ejecutable en PC o Raspberry Pi

**Backend (cloud):**
- Supabase (PostgreSQL + API REST)

**Control de versiones:**
- Git + GitHub

**Flujo básico:**

POS → Supabase → Reportes / Análisis

---

## 📂 Estructura del proyecto

```
Barbacoa/
│
├── app/
│   ├── main.py              # App principal POS
│   ├── ui/                   # Interfaces (comandas, gastos, cierre, etc.)
│   ├── services/             # Conexión Supabase y lógica backend
│   ├── domain/               # Lógica de negocio (cálculos, modelos)
│
├── sql/
│   ├── schema.sql            # Esquema de base de datos Supabase
│
├── scripts/
│   ├── install_pi.sh         # Instalación en Raspberry Pi (futuro)
│   ├── update_pi.sh          # Actualización del sistema (futuro)
│
├── .env.example              # Variables de entorno de ejemplo
├── requirements.txt          # Dependencias Python
├── README.md                 # Documentación del proyecto
└── .gitignore
```

---

## 🗄️ Modelo de base de datos (Supabase)

Tablas principales:

- `productos` → catálogo de productos
- `comandas` → ventas
- `comanda_items` → productos por comanda
- `gastos` → gastos operativos
- `propinas` → propinas por mesero
- `cierres_caja` → cierre diario
- `meseros` → personal

El esquema completo se encuentra en:

```
sql/schema.sql
```

---

## ⚙️ Configuración del proyecto

### 1) Clonar repositorio

```bash
git clone git@github.com:DiegoSanMo6011/Barbacoa.git
cd Barbacoa
```

### 2) Crear entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4) Configurar variables de entorno

Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

Edita `.env` y agrega las credenciales de Supabase:

```env
SUPABASE_URL=https://rwbzbaenzfqnstxsuxrl.supabase.co
SUPABASE_ANON_KEY=TU_ANON_KEY_AQUI
```

⚠️ Nunca subas `.env` al repositorio.

---

### 5) Ejecutar el POS

```bash
python app/main.py
```

---

## 🧩 Módulos del sistema

### ✅ Implementado (MVP)

- Comandas
- Métodos de pago
- Cálculo de totales y cambio
- Persistencia en Supabase

### 🚧 En desarrollo

- Gastos
- Propinas
- Cierre de caja
- Reportes
- Instalación en Raspberry Pi

Nota: el módulo de Reportes exporta CSV en la carpeta `exports/` (se crea automáticamente al exportar).

---

## 👥 Organización del equipo

Cada módulo se desarrolla en ramas independientes:

### Crear rama

```bash
git checkout -b feature/nombre_modulo
```

### Subir cambios

```bash
git add .
git commit -m "feat: descripcion del modulo"
git push -u origin feature/nombre_modulo
```

Luego se crea un Pull Request hacia `main`.

---

## 📌 Plan de desarrollo (corto plazo)

Objetivo: sistema completo en 2–3 días.

Módulos asignados:

- Gastos → Crazyhand
- Cierre de caja → ArturoProgamer777
- Propinas, reportes e integración → Gera

---

## 📊 Uso de datos demo

Si falta información real del restaurante (categorías, productos, tipos de gasto, etc.), se deben usar datos de ejemplo claros.

Cuando se requiera información real:
- Notificar a Gera.
- Gera se encarga de consultar al cliente.
- Se actualiza el sistema.

---

## 🚀 Roadmap futuro

- Impresión de tickets
- Roles de usuario (cajero / admin)
- Dashboard web
- Modo offline
- Analítica avanzada
- Empaquetado como ejecutable
- Actualización remota en Raspberry Pi

---

## 📎 Nota importante

La prioridad del proyecto es:

1. Funcionalidad real
2. Estabilidad
3. Simplicidad operativa
4. Escalabilidad futura

Primero que funcione bien en el negocio, luego se optimiza.

---
