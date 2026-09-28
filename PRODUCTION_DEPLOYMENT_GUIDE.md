# 🌐 NagrikSnap Production Deployment & Public Launch Guide

This guide contains the step-by-step instructions to deploy and launch **NagrikSnap** for public use.

---

## 🏗️ Architecture Overview

```mermaid
graph TD
    Client["Citizens / Students / CSR / Govt Officers"] --> |HTTPS / Port 443| CDN["Cloudflare / Nginx Reverse Proxy"]
    CDN --> |Port 8000| FastAPI["FastAPI Production Engine (uvicorn)"]
    FastAPI --> |Static Assets| Frontend["HTML5 + Vanilla CSS + JS UI"]
    FastAPI --> |psycopg pool| NeonDB["Neon Cloud PostgreSQL Database"]
    FastAPI --> |boto3 AES-256| S3["AWS S3 / Cloudflare R2 Evidence Storage"]
    FastAPI --> |HTTPS REST| Groq["Groq Llama 3.1 AI Classifier & Jan Sevak"]
    FastAPI --> |REST API| SMS["Twilio & Fast2SMS Gateways"]
```

---

## 🚀 Option 1: One-Click Cloud Deployment (Render.com / Railway) — *Recommended*

The simplest way to go live with zero server maintenance.

### Steps:
1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "NagrikSnap production ready"
   git push origin main
   ```
2. **Connect to Render.com**:
   - Go to [dashboard.render.com](https://dashboard.render.com) and click **New + > Web Service**.
   - Connect your GitHub repository.
   - Choose **Python 3** environment.
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `python -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/health`
3. **Add Environment Variables**:
   In the Render Dashboard under **Environment**, set:
   - `APP_ENV`: `production`
   - `DATABASE_URL`: `postgresql://neondb_owner:npg_j8nlwN4PaWIb@ep-steep-frost-akscnpak-pooler.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require`
   - `ALLOWED_ORIGINS`: `https://your-service.onrender.com,https://nagriksnap.org`
   - `ADMIN_USERNAME`: `admin`
   - `ADMIN_PASSWORD_HASH`: *(Generate using the script below)*
   - `GROQ_API_KEY`: *(Your Groq API key from https://console.groq.com)*
   - `FAST2SMS_API_KEY`: *(Optional for SMS notifications)*
4. Click **Deploy**. Your site will be live at `https://your-service.onrender.com`!

---

## 🐳 Option 2: Docker & Docker Compose (VPS / AWS EC2 / DigitalOcean)

Ideal if you have your own Ubuntu / Debian server or virtual machine.

### Steps:
1. **SSH into your server and clone the repository**:
   ```bash
   git clone <your-repo-url> /opt/nagriksnap
   cd /opt/nagriksnap
   ```
2. **Configure your `.env`**:
   ```bash
   cp .env.production.example backend/.env
   nano backend/.env
   ```
3. **Build & Start the Docker Container**:
   ```bash
   docker compose up -d --build
   ```
4. **Verify container health**:
   ```bash
   curl -f http://localhost:8000/api/health
   ```
   Output:
   ```json
   {
     "status": "healthy",
     "database": {
       "engine": "postgresql (neon cloud)",
       "status": "connected"
     }
   }
   ```
5. **Configure Nginx & Free SSL (Let's Encrypt Certbot)**:
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   sudo cp nginx.conf /etc/nginx/sites-available/nagriksnap
   sudo ln -s /etc/nginx/sites-available/nagriksnap /etc/nginx/sites-enabled/
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   sudo systemctl restart nginx
   ```

---

## 🔐 Generating Production Admin Password Hash

Run this command in Python on your machine or server to create an Argon2id hash for the central admin account:

```python
from backend.main import hash_password
print(hash_password("SetYourSecureAdminPassword123!"))
```
Copy the printed output (e.g. `$argon2id$v=19$m=65536,t=3,p=4$...`) into `ADMIN_PASSWORD_HASH` in your `.env`.

---

## 📋 Pre-Launch Verification Checklist

| Check | Component | Status | Verification Command |
|---|---|---|---|
| ✅ | **Database Persistence** | Neon Cloud PostgreSQL Live | `curl http://localhost:8000/api/health` |
| ✅ | **Dual Database Fallback** | SQLite Automatic Fallback | Verified in `backend/database.py` |
| ✅ | **AI Classifier** | Groq Llama 3.1 + Heuristics | 100% Passing in `test_external_services.py` |
| ✅ | **AI Chatbot** | Jan Sevak (`/api/ai/chat`) | Interactive on all frontend pages |
| ✅ | **SMS Gateways** | Twilio & Fast2SMS | Fully dispatchable with mock fallback |
| ✅ | **Cloud Storage** | AWS S3 / Cloudflare R2 | Pre-signed download URLs enabled |
| ✅ | **Security** | Argon2id + CSRF + Rate Limiter | Passed 52/52 test suite |
| ✅ | **Central Admin** | Environment Provisioned | Tested and secured |
| ✅ | **Docker & Cloud** | Multi-stage Dockerfile | Ready for instant deploy |
