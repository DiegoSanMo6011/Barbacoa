#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSL_DIR="${ROOT_DIR}/deploy/nginx/ssl"

DOMAIN="pos-lite.local"
IP_ADDR=""
CA_DAYS=3650
CERT_DAYS=825

usage() {
  cat <<'EOF'
Uso:
  ./scripts/gen-local-cert.sh --ip <IP_LOCAL_POS> [--domain pos-lite.local]

Opciones:
  --ip        IP local del servidor POS (requerida)
  --domain    Dominio local del certificado (default: pos-lite.local)
  --help      Muestra ayuda
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ip)
      IP_ADDR="${2:-}"
      shift 2
      ;;
    --domain)
      DOMAIN="${2:-}"
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

if [[ -z "${IP_ADDR}" ]]; then
  echo "Error: debes indicar --ip <IP_LOCAL_POS>" >&2
  usage
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "Error: openssl no está instalado." >&2
  exit 1
fi

mkdir -p "${SSL_DIR}"

CA_KEY="${SSL_DIR}/local-ca.key"
CA_CRT="${SSL_DIR}/local-ca.crt"
SRV_KEY="${SSL_DIR}/pos-lite.key"
SRV_CSR="${SSL_DIR}/pos-lite.csr"
SRV_CRT="${SSL_DIR}/pos-lite.crt"
SRV_EXT="${SSL_DIR}/pos-lite.ext"

openssl genrsa -out "${CA_KEY}" 4096
openssl req -x509 -new -nodes \
  -key "${CA_KEY}" \
  -sha256 \
  -days "${CA_DAYS}" \
  -subj "/CN=AutoNoma POS Lite Local CA" \
  -out "${CA_CRT}"

openssl genrsa -out "${SRV_KEY}" 2048
openssl req -new \
  -key "${SRV_KEY}" \
  -subj "/CN=${DOMAIN}" \
  -out "${SRV_CSR}"

cat > "${SRV_EXT}" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names
[alt_names]
DNS.1=${DOMAIN}
IP.1=${IP_ADDR}
EOF

openssl x509 -req \
  -in "${SRV_CSR}" \
  -CA "${CA_CRT}" \
  -CAkey "${CA_KEY}" \
  -CAcreateserial \
  -out "${SRV_CRT}" \
  -days "${CERT_DAYS}" \
  -sha256 \
  -extfile "${SRV_EXT}"

chmod 600 "${CA_KEY}" "${SRV_KEY}"
chmod 644 "${CA_CRT}" "${SRV_CRT}"

rm -f "${SRV_CSR}" "${SRV_EXT}" "${SSL_DIR}/local-ca.srl"

cat <<EOF
✅ Certificados generados en ${SSL_DIR}
- CA:         local-ca.crt
- Server CRT: pos-lite.crt
- Server KEY: pos-lite.key

Siguiente paso:
1) Instala local-ca.crt en Android/iOS
2) Levanta stack: ./scripts/prod-up.sh
EOF
