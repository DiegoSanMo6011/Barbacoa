# Despliegue Local Seguro (Laptop → Raspberry)

Esta guía instala AutoNoma POS Lite en red local, con HTTPS y sin exponer servicios a internet.

## 1) Prerrequisitos

- Ubuntu/Debian (laptop o Raspberry Pi OS)
- Docker + Docker Compose plugin
- `openssl`
- Archivo `lite-edge/.env` configurado con valores reales

## 2) Preparar variables seguras

```bash
cd lite-edge
cp .env.example .env
```

Valores críticos:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `TENANT_ID`
- `SECRET_KEY` (largo y aleatorio)
- `PIN_CAJERO`, `PIN_ADMIN`
- `ALLOW_ORIGINS` (incluye `https://pos-lite.local`)

Recomendado:
```bash
chmod 600 lite-edge/.env
```

## 3) Generar certificados TLS locales

```bash
./scripts/gen-local-cert.sh --ip <IP_LOCAL_POS> --domain pos-lite.local
```

Archivos generados:
- `deploy/nginx/ssl/local-ca.crt`
- `deploy/nginx/ssl/pos-lite.crt`
- `deploy/nginx/ssl/pos-lite.key`

## 4) Levantar stack productivo

```bash
./scripts/prod-up.sh
```

Servicios:
- `web` (Nginx) publica `80/443`
- `edge` solo interno (`8000`)
- `pwa` genera assets estáticos para Nginx

## 5) Acceso desde monitor o móvil

- URL principal: `https://pos-lite.local`
- URL alternativa: `https://<IP_LOCAL_POS>`

### Android
1. Copia `local-ca.crt` al teléfono.
2. Instala certificado CA desde ajustes de seguridad.
3. Abre `https://pos-lite.local` y agrega a pantalla de inicio.

### iOS
1. Envía `local-ca.crt` al iPhone.
2. Instala el perfil.
3. Activa confianza en:
   `Settings > General > About > Certificate Trust Settings`
4. Abre `https://pos-lite.local` y agrega a inicio (Share > Add to Home Screen).

## 6) Hardening del host (obligatorio)

### Firewall (UFW)

```bash
# Opción rápida automatizada:
sudo ./scripts/hardening-host.sh --lan-cidr 192.168.0.0/16 --admin-ip <IP_ADMIN>

# Variante recomendada con Tailscale para soporte remoto:
sudo ./scripts/hardening-host.sh --lan-cidr 192.168.0.0/16 --ssh-cidr 100.64.0.0/10

# Opción manual:
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.0.0/16 to any port 443 proto tcp
sudo ufw allow from <IP_ADMIN> to any port 22 proto tcp
sudo ufw enable
sudo ufw status verbose
```

No abrir:
- `8000/tcp`
- `5173/tcp`

Soporte remoto:
- Preferir Tailscale (tailnet privado) en vez de exponer SSH público.

### SSH seguro

Editar `/etc/ssh/sshd_config`:
- `PasswordAuthentication no`
- `PermitRootLogin no`
- `PubkeyAuthentication yes`

Reiniciar:
```bash
sudo systemctl restart ssh
```

### Parches de seguridad

```bash
sudo apt update
sudo apt install -y unattended-upgrades fail2ban
sudo systemctl enable --now unattended-upgrades
sudo systemctl enable --now fail2ban
timedatectl status
```

## 7) Operación kiosko (monitor opcional)

En equipo con GUI:
- Arranca Chromium en fullscreen con `https://pos-lite.local`.
- Configura autostart de sesión para iniciar directo al POS.

## 8) Migración 1:1 a Raspberry

1. Copia repo y `.env`.
2. Instala Docker + Compose.
3. Genera cert con IP de Raspberry.
4. Ejecuta `./scripts/prod-up.sh`.
5. Reinstala `local-ca.crt` en móviles.

## 9) Verificación rápida

```bash
docker compose -f deploy/docker-compose.prod.yml ps
curl -k https://localhost/
curl -k https://localhost/api/status
```

Esperado:
- Nginx responde por `443`
- API responde `status: ok`
- Catálogo/ventas funcionan en móvil y monitor
