#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso:
  sudo ./scripts/hardening-host.sh --lan-cidr 192.168.0.0/16 --admin-ip 192.168.1.10
  sudo ./scripts/hardening-host.sh --lan-cidr 192.168.0.0/16 --ssh-cidr 100.64.0.0/10

Opciones:
  --lan-cidr   CIDR LAN autorizada para HTTPS (443) [requerido]
  --admin-ip   IP administrativa autorizada para SSH (22) [opcional]
  --ssh-cidr   CIDR autorizada para SSH (22), útil para Tailscale [opcional]
  --help       Muestra ayuda
EOF
}

LAN_CIDR=""
ADMIN_IP=""
SSH_CIDR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lan-cidr)
      LAN_CIDR="${2:-}"
      shift 2
      ;;
    --admin-ip)
      ADMIN_IP="${2:-}"
      shift 2
      ;;
    --ssh-cidr)
      SSH_CIDR="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Argumento no reconocido: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${LAN_CIDR}" ]]; then
  echo "Error: --lan-cidr es requerido." >&2
  usage
  exit 1
fi

if [[ -z "${ADMIN_IP}" && -z "${SSH_CIDR}" ]]; then
  echo "Error: define --admin-ip o --ssh-cidr para acceso SSH." >&2
  usage
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Error: este script debe correr con sudo/root." >&2
  exit 1
fi

apt-get update
apt-get install -y ufw fail2ban unattended-upgrades

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow from "${LAN_CIDR}" to any port 443 proto tcp
if [[ -n "${ADMIN_IP}" ]]; then
  ufw allow from "${ADMIN_IP}" to any port 22 proto tcp
fi
if [[ -n "${SSH_CIDR}" ]]; then
  ufw allow from "${SSH_CIDR}" to any port 22 proto tcp
fi
ufw --force enable

systemctl enable --now fail2ban
systemctl enable --now unattended-upgrades

cat <<'EOF'
✅ Hardening aplicado:
- UFW: deny incoming + allow 443 LAN + allow 22 admin/tailnet
- fail2ban activo
- unattended-upgrades activo

Siguiente paso:
1) Verifica SSH hardening en /etc/ssh/sshd_config:
   PasswordAuthentication no
   PermitRootLogin no
2) Reinicia SSH: sudo systemctl restart ssh
EOF
