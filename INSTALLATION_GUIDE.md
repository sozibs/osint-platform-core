# Installation Guide – OSINT Platform

## Prerequisites

| Component | Minimum Version |
|---|---|
| Docker | 24.x |
| Docker Compose | 2.x |
| Node.js (dev only) | 22.x |
| Python (dev only) | 3.12 |

---

## Option 1: Docker Compose (Recommended)

### 1. Clone the repository

```bash
git clone https://github.com/sozibs/osint-platform-core.git
cd osint-platform-core
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set at minimum:
#   SECRET_KEY=<random 32-char string>
#   VAPID_PRIVATE_KEY=<generated>
#   VAPID_PUBLIC_KEY=<generated>
```

Generate VAPID keys:

```bash
cd backend
pip install cryptography
python - <<'EOF'
from notifications.vapid_keys import get_vapid_keys
keys = get_vapid_keys()
print("VAPID_PRIVATE_KEY=" + keys["private_key"])
print("VAPID_PUBLIC_KEY=" + keys["public_key"])
EOF
```

### 3. Generate app icons (optional)

```bash
# Place a 1024×1024 source icon at assets/icon-source.png
bash scripts/generate-icons.sh
```

### 4. Start the platform

```bash
docker compose up -d
```

The platform is now available at **http://localhost**.

---

## Option 2: Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL and Redis (or use Docker):
docker compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start API server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

The Vite dev server proxies `/api` requests to `http://localhost:8000`.

---

## Option 3: Production (HTTPS + nginx)

### 1. Configure TLS certificates

Place your TLS certificate files at:

```
nginx/ssl/cert.pem
nginx/ssl/key.pem
```

For Let's Encrypt (Certbot):

```bash
certbot certonly --standalone -d osint-platform.com
cp /etc/letsencrypt/live/osint-platform.com/fullchain.pem nginx/ssl/cert.pem
cp /etc/letsencrypt/live/osint-platform.com/privkey.pem nginx/ssl/key.pem
```

### 2. Update `nginx/nginx.conf`

Set your domain name in the `server_name` directive.

### 3. Start the stack

```bash
docker compose up -d
```

The platform is now available at **https://osint-platform.com**.

---

## PWA Installation (End Users)

See [PWA_GUIDE.md](./PWA_GUIDE.md) for device-specific installation instructions.

---

## Verifying the Installation

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"1.0.0","environment":"production"}

# PWA manifest
curl http://localhost/manifest.json

# Service worker
curl -I http://localhost/sw.js
# Expected: Cache-Control: no-cache, no-store, must-revalidate
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Port 80/443 in use | Change `ports` in `docker-compose.yml` |
| Push notifications not working | Verify `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` are set |
| SW not updating | Hard-refresh (Ctrl+Shift+R) or clear site data in DevTools |
| iOS PWA install not available | Must use Safari; Chrome on iOS does not support install |
