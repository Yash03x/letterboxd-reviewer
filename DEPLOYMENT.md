# spyboxd.com — Deployment Guide

## Architecture

```
Browser → Cloudflare Pages (Next.js + Clerk) — spyboxd.com
               ↓ HTTPS
          Nginx :443 — api.spyboxd.com → Hetzner CX23 (116.203.81.242)
               ↓
          FastAPI uvicorn :8000 (2 workers)
               ↓ apply_async()
          Redis :6379 (localhost only)
               ↓
          Celery Worker (2 processes) + Celery Beat (3am UTC daily)
               ↓
          PostgreSQL :5432 (localhost only)
```

**Cost: ~€4.15/mo (Hetzner) + €0.60/mo (IPv4) = ~€5/mo total**

---

## Infrastructure

| Service | Provider | Cost |
|---------|----------|------|
| Backend VPS | Hetzner CX23 — Nuremberg | €4.15/mo |
| Static IPv4 | Hetzner | €0.60/mo |
| Frontend CDN | Cloudflare Pages | Free |
| Auth | Clerk (≤10k MAU) | Free |
| Domain | spyboxd.com (Cloudflare) | ~€1/mo |
| SSL | Let's Encrypt (auto-renew) | Free |

---

## One-Time VPS Setup

### 1. Create Hetzner Server

- Type: **CX23** (Cost-Optimized, x86, 2 vCPU, 4GB RAM, 40GB SSD)
- Location: **Nuremberg**
- Image: **Ubuntu 24.04**
- Networking: **IPv4 + IPv6** (no private network needed)
- SSH key: add your public key (`cat ~/.ssh/id_ed25519.pub`)

### 2. Create deploy user

```bash
ssh root@116.203.81.242

adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Passwordless sudo for CI/CD deploys
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy

# Disable root SSH login
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Verify deploy user works in a **new terminal tab** before closing root session:
```bash
ssh deploy@116.203.81.242
```

### 3. Install dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  postgresql postgresql-contrib \
  redis-server \
  python3.12 python3.12-venv python3-pip build-essential \
  nginx certbot python3-certbot-nginx \
  git
```

### 4. Configure PostgreSQL

```bash
sudo -u postgres psql <<EOF
CREATE DATABASE spyboxd;
CREATE USER spyboxd WITH PASSWORD 'your_strong_password_here';
GRANT ALL PRIVILEGES ON DATABASE spyboxd TO spyboxd;
\c spyboxd
GRANT ALL ON SCHEMA public TO spyboxd;
EOF
```

### 5. Configure Redis

```bash
sudo sed -i 's/^bind 127.0.0.1 -::1/bind 127.0.0.1/' /etc/redis/redis.conf
sudo systemctl enable redis-server && sudo systemctl restart redis-server
```

### 6. Clone repo and set up Python environment

```bash
sudo mkdir /opt/spyboxd
sudo chown deploy:deploy /opt/spyboxd
git clone https://github.com/Yash03x/letterboxd-reviewer /opt/spyboxd
cd /opt/spyboxd
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 7. Create production `.env`

```bash
cat > /opt/spyboxd/.env <<'EOF'
DATABASE_URL=postgresql+psycopg://spyboxd:your_strong_password_here@localhost/spyboxd
REDIS_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
FRONTEND_URL=https://spyboxd.com
CORS_ALLOWED_ORIGINS=https://spyboxd.com,https://www.spyboxd.com
CLERK_JWKS_URL=https://set-dove-61.clerk.accounts.dev/.well-known/jwks.json
LOG_LEVEL=INFO
DEBUG_MODE=false
EOF
```

### 8. Run database migrations

```bash
cd /opt/spyboxd
source .venv/bin/activate
PYTHONPATH=/opt/spyboxd/backend alembic upgrade head
```

### 9. Create systemd services

```bash
sudo tee /etc/systemd/system/spyboxd-api.service <<'EOF'
[Unit]
Description=spyboxd FastAPI
After=network.target postgresql.service redis-server.service

[Service]
User=deploy
WorkingDirectory=/opt/spyboxd/backend
EnvironmentFile=/opt/spyboxd/.env
ExecStart=/opt/spyboxd/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
Environment=PYTHONPATH=/opt/spyboxd/backend

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/spyboxd-worker.service <<'EOF'
[Unit]
Description=spyboxd Celery Worker
After=network.target redis-server.service

[Service]
User=deploy
WorkingDirectory=/opt/spyboxd/backend
EnvironmentFile=/opt/spyboxd/.env
ExecStart=/opt/spyboxd/.venv/bin/celery -A celery_app.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/spyboxd/backend

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/spyboxd-beat.service <<'EOF'
[Unit]
Description=spyboxd Celery Beat
After=network.target redis-server.service

[Service]
User=deploy
WorkingDirectory=/opt/spyboxd/backend
EnvironmentFile=/opt/spyboxd/.env
ExecStart=/opt/spyboxd/.venv/bin/celery -A celery_app.celery_app beat --loglevel=info
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/spyboxd/backend

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable spyboxd-api spyboxd-worker spyboxd-beat
sudo systemctl start spyboxd-api spyboxd-worker spyboxd-beat
```

Verify all three are running:
```bash
sudo systemctl status spyboxd-api spyboxd-worker spyboxd-beat --no-pager
```

### 10. Configure Nginx

```bash
sudo tee /etc/nginx/sites-available/api.spyboxd.com <<'EOF'
server {
    listen 80;
    server_name api.spyboxd.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 900s;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/api.spyboxd.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 11. Cloudflare DNS

In Cloudflare dashboard for `spyboxd.com` → DNS:
- Add `A` record: **Name:** `api` | **IPv4:** `116.203.81.242` | **Proxy:** DNS only (grey cloud)

### 12. SSL via Certbot

```bash
sudo certbot --nginx -d api.spyboxd.com
```

Enter your email, agree to terms. Certbot auto-renews via a systemd timer.

Verify:
```bash
curl https://api.spyboxd.com/health
# → {"status":"ok","timestamp":"..."}
```

---

## Cloudflare Pages (Frontend)

1. Cloudflare Dashboard → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
2. Select `Yash03x/letterboxd-reviewer`
3. Build settings:
   - **Framework preset:** Next.js
   - **Build command:** `cd frontend && npm ci && npm run build`
   - **Build output directory:** `frontend/.next`
4. Environment variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.spyboxd.com` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_live_...` |
| `CLERK_SECRET_KEY` | `sk_live_...` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/` |

5. Custom domain: add `spyboxd.com`

---

## GitHub Actions CI/CD

Every push to `main` automatically deploys to the VPS via SSH.

Add these secrets to the GitHub repo (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `VPS_HOST` | `116.203.81.242` |
| `VPS_SSH_KEY` | contents of `~/.ssh/id_ed25519` (private key) |

The deploy workflow is at [.github/workflows/deploy.yml](.github/workflows/deploy.yml).

---

## Admin Access

To grant yourself admin access (required to trigger manual scrapes):

1. Go to Clerk Dashboard → Users → select your user
2. Click **Metadata** → **Public metadata**
3. Set: `{"is_admin": true}`

---

## Daily Backup

Add to deploy user's crontab (`crontab -e`):

```cron
0 4 * * * pg_dump -U spyboxd spyboxd | gzip > /home/deploy/backups/$(date +\%Y\%m\%d).sql.gz
0 5 * * * find /home/deploy/backups/ -name "*.sql.gz" -mtime +7 -delete
```

```bash
mkdir -p /home/deploy/backups
```

---

## Useful Commands

```bash
# Check service status
sudo systemctl status spyboxd-api spyboxd-worker spyboxd-beat

# View live logs
sudo journalctl -u spyboxd-api -f
sudo journalctl -u spyboxd-worker -f

# Restart all services
sudo systemctl restart spyboxd-api spyboxd-worker spyboxd-beat

# Manual deploy (same as CI/CD)
cd /opt/spyboxd && git pull origin main
source .venv/bin/activate
pip install -r requirements.txt --quiet
PYTHONPATH=/opt/spyboxd/backend alembic upgrade head
sudo systemctl restart spyboxd-api spyboxd-worker spyboxd-beat
```

---

## Scaling

| When | Action | New cost |
|------|--------|----------|
| DB getting large / slow | Upgrade to CX33 (8GB RAM) | ~€6/mo |
| More scrape traffic | Increase `--concurrency` on Celery worker | Free |
| >10k users | Upgrade Clerk plan | €25/mo |
