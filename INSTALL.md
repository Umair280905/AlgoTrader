# AlgoTrader — Ubuntu Server Installation Guide

Tested on **Ubuntu 22.04 LTS**. Run all commands as a non-root user with `sudo` access.

---

## 1. System Dependencies

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    python3.11 python3.11-venv python3.11-dev \
    build-essential git curl \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    supervisor
```

Confirm Python version:

```bash
python3.11 --version
```

---

## 2. Create a Dedicated System User

```bash
sudo useradd -m -s /bin/bash algotrader
sudo su - algotrader
```

All remaining steps are run as the `algotrader` user unless noted.

---

## 3. Clone the Repository

```bash
git clone <your-repo-url> ~/AlgoTrading
cd ~/AlgoTrading
```

---

## 4. Python Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip wheel
pip install -r requirements.txt
```

> The `neo-api-client` package installs directly from GitHub (pinned commit) as listed in `requirements.txt`. Make sure `git` is available — it is installed in step 1.

---

## 5. PostgreSQL Setup

```bash
sudo -u postgres psql
```

Inside the psql shell:

```sql
CREATE USER algotrader WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE algo_trader OWNER algotrader;
GRANT ALL PRIVILEGES ON DATABASE algo_trader TO algotrader;
\q
```

---

## 6. Redis

Redis is already installed. Enable and start it:

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

---

## 7. Environment Configuration

```bash
cp .env.example .env
nano .env
```

Fill in every value:

```ini
# Django
SECRET_KEY=replace-with-a-long-random-string
DEBUG=False
ALLOWED_HOSTS=your-server-ip,yourdomain.com

# Database
DB_NAME=algo_trader
DB_USER=algotrader
DB_PASSWORD=choose-a-strong-password
DB_HOST=localhost
DB_PORT=5432

# Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Kotak Neo (get from https://developer.kotaksecurities.com/)
KOTAK_CONSUMER_KEY=your-consumer-key
KOTAK_CONSUMER_SECRET=your-consumer-secret
KOTAK_NEO_FIN_KEY=your-neo-fin-key
KOTAK_ACCESS_TOKEN=          # filled by kotak_login command each morning
KOTAK_MOBILE=your-registered-mobile
KOTAK_PASSWORD=your-trading-password

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Trading Engine
PAPER_TRADING=True           # set False only when ready for live trading
PHASE=1
MAX_DAILY_LOSS_INR=500
MAX_OPEN_POSITIONS=3
MAX_PER_STRATEGY=1
RISK_PER_TRADE_PCT=0.01
MINIMUM_CASH_BUFFER=10000

# Anthropic (optional AI features)
ANTHROPIC_API_KEY=
AI_ENABLED=False
AI_MIN_CONFIDENCE=60
```

Generate a Django secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 8. Django Setup

```bash
source venv/bin/activate
cd ~/AlgoTrading

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Verify the app starts:

```bash
python manage.py runserver 0.0.0.0:8000
# Press Ctrl+C to stop after confirming it loads
```

---

## 9. Gunicorn

Install Gunicorn (add it to your venv):

```bash
pip install gunicorn
```

Test it manually:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
# Ctrl+C to stop
```

---

## 10. Supervisor — Process Management

Supervisor keeps Gunicorn, Celery worker, and Celery beat alive across reboots and restarts them on crash.

Create the config file (run as `sudo`):

```bash
sudo nano /etc/supervisor/conf.d/algotrader.conf
```

Paste the following — replace `/home/algotrader/AlgoTrading` and `/home/algotrader` with your actual paths:

```ini
[program:algotrader_web]
command=/home/algotrader/AlgoTrading/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
directory=/home/algotrader/AlgoTrading
user=algotrader
autostart=true
autorestart=true
stderr_logfile=/var/log/algotrader/web.err.log
stdout_logfile=/var/log/algotrader/web.out.log
environment=DJANGO_SETTINGS_MODULE="config.settings"

[program:algotrader_celery_worker]
command=/home/algotrader/AlgoTrading/venv/bin/celery -A config worker --loglevel=info --concurrency=2
directory=/home/algotrader/AlgoTrading
user=algotrader
autostart=true
autorestart=true
stopwaitsecs=10
stderr_logfile=/var/log/algotrader/celery_worker.err.log
stdout_logfile=/var/log/algotrader/celery_worker.out.log

[program:algotrader_celery_beat]
command=/home/algotrader/AlgoTrading/venv/bin/celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/home/algotrader/AlgoTrading
user=algotrader
autostart=true
autorestart=true
stderr_logfile=/var/log/algotrader/celery_beat.err.log
stdout_logfile=/var/log/algotrader/celery_beat.out.log

[group:algotrader]
programs=algotrader_web,algotrader_celery_worker,algotrader_celery_beat
```

Create the log directory and reload supervisor:

```bash
sudo mkdir -p /var/log/algotrader
sudo chown algotrader:algotrader /var/log/algotrader

sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start algotrader:*
sudo supervisorctl status
```

---

## 11. Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/algotrader
```

```nginx
server {
    listen 80;
    server_name your-server-ip yourdomain.com;

    location /static/ {
        alias /home/algotrader/AlgoTrading/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

Enable the site and reload:

```bash
sudo ln -s /etc/nginx/sites-available/algotrader /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 12. Kotak Neo — Daily Login (Each Trading Morning)

Kotak Neo uses an OTP-based session that expires daily. Run this each morning **before** starting live trading:

```bash
cd ~/AlgoTrading
source venv/bin/activate
python manage.py kotak_login
```

The command will:
1. Trigger an OTP to your registered mobile number
2. Prompt you to enter the OTP
3. Print the new `KOTAK_ACCESS_TOKEN`

Copy the token into your `.env` file:

```bash
nano .env
# Update: KOTAK_ACCESS_TOKEN=<paste token here>
```

Then restart the processes to pick up the new token:

```bash
sudo supervisorctl restart algotrader:*
```

---

## 13. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 14. (Optional) HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
sudo systemctl reload nginx
```

Certbot sets up auto-renewal automatically.

---

## 15. Useful Commands

| Task | Command |
|------|---------|
| View all process status | `sudo supervisorctl status` |
| Restart everything | `sudo supervisorctl restart algotrader:*` |
| Tail web logs | `tail -f /var/log/algotrader/web.out.log` |
| Tail Celery logs | `tail -f /var/log/algotrader/celery_worker.out.log` |
| Django shell | `python manage.py shell` |
| Run migrations | `python manage.py migrate` |
| Start trading | `python manage.py start_trading` |
| Kotak daily login | `python manage.py kotak_login` |

---

## 16. Service Startup Order

On a fresh boot, the correct startup order is handled automatically by supervisor and systemd:

1. PostgreSQL → started by systemd
2. Redis → started by systemd
3. Gunicorn (web) → started by supervisor
4. Celery worker → started by supervisor
5. Celery beat → started by supervisor

Every morning before live trading:

```
kotak_login → update .env → supervisorctl restart algotrader:*
```
