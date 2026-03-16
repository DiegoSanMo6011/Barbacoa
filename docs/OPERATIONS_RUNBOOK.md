# Runbook de Operación — POS Lite

## 1) Monitoreo local y alertas

Ejecuta healthcheck manual:

```bash
./scripts/monitor-health.sh
```

Con alertas Telegram:

```bash
ALERT_TELEGRAM_BOT_TOKEN="..." \
ALERT_TELEGRAM_CHAT_ID="..." \
./scripts/monitor-health.sh
```

Con alerta email (si `mail` está disponible):

```bash
ALERT_EMAIL="ops@mi-dominio.com" ./scripts/monitor-health.sh
```

Cron recomendado (cada minuto):

```bash
* * * * * cd /ruta/pos_lite && ./scripts/monitor-health.sh >> /var/log/pos-lite-health.log 2>&1
```

## 2) Backups de configuración local

Backup cifrado:

```bash
BACKUP_PASSPHRASE="clave-larga" ./scripts/backup-local-config.sh
```

Restore desde backup cifrado:

```bash
openssl enc -d -aes-256-cbc -pbkdf2 \
  -in backups/pos_lite_config_YYYYMMDDTHHMMSSZ.tar.gz.enc \
  -out /tmp/restore.tar.gz \
  -pass pass:"clave-larga"

tar -xzf /tmp/restore.tar.gz -C /ruta/pos_lite
```

## 3) Soporte remoto seguro (Tailscale)

1. Instala Tailscale en host POS y equipo de soporte.
2. Une ambos al mismo tailnet.
3. Restringe SSH con `--ssh-cidr 100.64.0.0/10`:

```bash
sudo ./scripts/hardening-host.sh --lan-cidr 192.168.0.0/16 --ssh-cidr 100.64.0.0/10
```

4. No expongas `8000/5173` públicamente.

## 4) Checklist mensual de restore drill

1. Restaurar backup de config en entorno de staging.
2. Levantar con `./scripts/prod-up.sh`.
3. Verificar:
   - `curl -k https://localhost/`
   - `curl -k https://localhost/api/status`
   - Flujo unlock → abrir jornada → cobrar → cerrar jornada.
4. Documentar fecha y tiempo de recuperación.
