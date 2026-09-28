"""
CivicInnovate / SamadhanSetu Backend - FastAPI
Built for SIH 2026 Problem Statement 26043:
"A digital platform to crowdsource societal challenges and facilitate collaborative problem solving through universities and industry partnerships"
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import os
import uuid
from datetime import datetime, timedelta
import json
import requests
import hashlib
import secrets
import hmac
import re
import time
import math
import smtplib
from email.message import EmailMessage

import database as db
import storage as evidence_storage

# Optional: Groq AI
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Fail closed for common deployment misconfiguration. TLS termination must be
# provided by the deployment proxy/load balancer; this app does not terminate TLS.
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV == "production":
    # Validate deployment configuration before the explicit release gate, so operators
    # receive actionable configuration errors rather than unreachable checks.
    if not os.getenv("ALLOWED_ORIGINS", "").strip():
        raise RuntimeError("APP_ENV=production requires explicit ALLOWED_ORIGINS")
    _prod_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if not _prod_origins or any(o == "*" or not o.startswith("https://") for o in _prod_origins):
        raise RuntimeError("Production ALLOWED_ORIGINS must contain only exact https:// origins")
    if not os.getenv("ADMIN_USERNAME", "").strip() or not os.getenv("ADMIN_PASSWORD_HASH", "").strip():
        raise RuntimeError("Production requires an out-of-band ADMIN_USERNAME and ADMIN_PASSWORD_HASH")
    if not getattr(db, "IS_POSTGRES", False):
        raise RuntimeError(
            "Production launch blocked: PostgreSQL application persistence is required. "
            "Please configure DATABASE_URL in .env to a verified PostgreSQL database instance."
        )

app = FastAPI(
    title="NagrikSnap API",
    description="Crowdsource Societal Challenges & Facilitate University-Industry Collaborative Problem Solving",
    version="2.0"
)

# CORS configuration
_ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip() and o.strip() != "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
# Local directory is only used when EVIDENCE_STORAGE_MODE=local (development).
evidence_storage.validate_configuration()
if evidence_storage.STORAGE_MODE == "local":
    os.makedirs(evidence_storage.LOCAL_UPLOAD_DIR, exist_ok=True)

# Admin default configuration
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
# Server-side bearer sessions are revocable. Default to an 8-hour session;
# operators may configure 5 minutes through 7 days via SESSION_TTL_SECONDS.
try:
    SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "28800"))
except ValueError as exc:
    raise RuntimeError("SESSION_TTL_SECONDS must be an integer") from exc
if not 300 <= SESSION_TTL_SECONDS <= 604800:
    raise RuntimeError("SESSION_TTL_SECONDS must be between 300 and 604800 seconds")
if APP_ENV == "production" and SESSION_TTL_SECONDS > 86400:
    raise RuntimeError("Production SESSION_TTL_SECONDS must not exceed 86400 seconds")
# No built-in administrator account or default password. Provision an admin out-of-band.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp"}


otp_store = {}



@app.middleware("http")
async def security_headers_and_auth_throttle(request: Request, call_next):
    if request.url.path in {"/auth/login", "/auth/demo-login", "/auth/register", "/auth/password-reset", "/api/ai-match", "/api/organization-verification"} or request.url.path.startswith("/uploads/") or (request.method == "POST" and request.url.path in {"/api/challenges", "/complaints"}):
        ip = request.client.host if request.client else "unknown"
        raw_bucket = f"{ip}:{request.method}:{request.url.path}"
        bucket_hash = hashlib.sha256(raw_bucket.encode()).hexdigest()
        limit = 10 if request.url.path in {"/auth/login", "/auth/demo-login", "/auth/register"} else 20
        try:
            allowed = db.consume_rate_limit(bucket_hash, limit, 60)
        except Exception:
            # Fail closed for protected/high-abuse endpoints if limiter storage fails.
            return JSONResponse(status_code=503, content={"detail": "Request protection temporarily unavailable."})
        if not allowed:
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Try again in a minute."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    return response


# ===== Geo & Admin Utility =====
def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except (ValueError, TypeError):
        return None
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_admin(lat, lng, department: str = ""):
    users = db.get_users()
    admins = [u for u in users if u.get("role") in ("admin", "govt_admin") and u.get("lat") and u.get("lng")]
    if not admins:
        return None
    scored = []
    for a in admins:
        dist = haversine_km(lat, lng, a.get("lat"), a.get("lng"))
        if dist is None:
            continue
        same_dept = 0 if (department and a.get("department") and department.lower() in str(a.get("department")).lower()) else 50
        scored.append((dist + same_dept, dist, a))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0])
    best = scored[0]
    return {
        "admin_id": best[2].get("id"),
        "admin_name": best[2].get("name"),
        "admin_phone": best[2].get("phone"),
        "admin_department": best[2].get("department"),
        "distance_km": round(best[1], 2),
    }


# ===== Auth Helpers =====
def create_token(username: str, role: str, user_id: str = "") -> str:
    token = secrets.token_urlsafe(32)
    expires = time.time() + SESSION_TTL_SECONDS
    db.create_session(hashlib.sha256(token.encode()).hexdigest(), username, role, user_id, expires)
    return token


def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:].strip()
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    data = db.get_session(hashlib.sha256(token.encode()).hexdigest())
    if not data:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    account = db.get_user_by_id(data.get("user_id")) if data.get("user_id") else None
    if account:
        # Authorization claims are sourced from the current account record so a
        # role downgrade/revocation takes effect for already-issued sessions.
        data["role"] = account.get("role", "citizen")
        data["organization"] = account.get("organization", "")
        data["department"] = account.get("department", "")
    else:
        data["organization"] = ""
        data["department"] = ""
    return data


def hash_password(password: str) -> str:
    if not password or len(password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters")
    try:
        from argon2 import PasswordHasher
        return PasswordHasher().hash(password)
    except ImportError as exc:
        raise RuntimeError("Install argon2-cffi before starting the API") from exc


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    # Verify modern Argon2 hashes. Legacy salted SHA-256 hashes are accepted only
    # to allow a successful login to migrate them to Argon2 immediately.
    if stored.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher
            return PasswordHasher().verify(stored, password)
        except Exception:
            return False
    if ":" in stored:
        salt, expected = stored.split(":", 1)
        return hmac.compare_digest(hashlib.sha256((salt + password).encode()).hexdigest(), expected)
    return False


def require_roles(*roles):
    def dependency(user=Depends(verify_token)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return user
    return dependency


def require_case_member(user=Depends(verify_token)):
    # Authentication alone is not case-room membership. The endpoint performs
    # challenge-specific authorization with can_access_case_room().
    if user.get("role") not in {"admin", "govt_admin", "university", "industry", "citizen"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


def can_access_case_room(challenge_id: str, user: dict) -> bool:
    role = user.get("role")
    if role in {"admin", "govt_admin"}:
        return True
    challenge = db.get_complaint_by_id(challenge_id)
    if not challenge:
        return False
    org = str(user.get("organization") or "").strip().casefold()
    if role == "university":
        return bool(org and (org == str(challenge.get("assigned_university") or "").strip().casefold()
            or any(str(p.get("university_name") or "").strip().casefold() == org for p in db.get_proposals(challenge_id))))
    if role == "industry":
        if org and any(str(x.get("company_name") or "").strip().casefold() == org for x in db.get_sponsorships(challenge_id)):
            return True
    # Accepted collaboration members can access only the challenge they joined.
    membership = db.get_collaboration_member(challenge_id, user.get("user_id", "")) if user.get("user_id") else None
    return bool(membership and membership.get("status") == "accepted")


def audit_action(user: dict, action: str, resource_type: str, resource_id: str, request: Request = None):
    db.log_audit({"actor_id": user.get("user_id", ""), "actor_name": user.get("username", ""),
        "actor_role": user.get("role", ""), "action": action, "resource_type": resource_type,
        "resource_id": resource_id, "ip_address": request.client.host if request and request.client else "", 
        "created_at": datetime.now().isoformat()})



# ===== SMS Service (Supports Twilio & Fast2SMS) =====
def send_sms(phone: str, message: str) -> dict:
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_from = os.getenv("TWILIO_FROM_PHONE", "").strip()
    if twilio_sid and twilio_token and twilio_from:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            formatted_phone = phone.strip()
            if not formatted_phone.startswith("+"):
                formatted_phone = f"+91{formatted_phone}"
            resp = requests.post(
                url,
                auth=(twilio_sid, twilio_token),
                data={"From": twilio_from, "To": formatted_phone, "Body": message[:160]},
                timeout=10
            )
            data = resp.json()
            return {"success": resp.status_code in {200, 201}, "provider": "twilio", "data": data}
        except Exception as e:
            print(f"[Twilio SMS Error] {e}")
            return {"success": False, "provider": "twilio", "error": str(e)}

    api_key = os.getenv("FAST2SMS_API_KEY", "").strip()
    if api_key:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {
                "authorization": api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "route": "q",
                "message": message[:160],
                "language": "english",
                "numbers": phone.replace("+91", "").strip()
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=8)
            data = resp.json()
            return {"success": data.get("return", False), "provider": "fast2sms", "data": data}
        except Exception as e:
            print(f"[Fast2SMS Error] {e}")
            return {"success": False, "provider": "fast2sms", "error": str(e)}

    print(f"[SMS SIMULATION] To: {phone} | Msg: {message}")
    return {"success": True, "simulated": True, "message": "SMS simulated (no FAST2SMS or TWILIO keys configured)"}


# ===== AI Societal Challenge Classifier & Matchmaker =====
def classify_societal_challenge(text: str, title: str = ""):
    combined = f"{title} {text}".lower()

    # Rule-based defaults
    category = "Civic Infrastructure"
    department = "Public Works & Urban Development"
    sdg_tag = "SDG 11: Sustainable Cities & Communities"
    priority = "Medium"
    ai_tech_stack = "IoT Sensors, Web Dashboard, Mobile App"
    ai_recommended_depts = "Computer Science, Civil Engineering, Electronics"
    ai_summary = text[:150] + ("..." if len(text) > 150 else "")

    if any(w in combined for w in ["water", "leak", "pipeline", "drain", "sewage", "drinking", "paani", "contamination", "jal"]):
        category = "Water & Sanitation"
        department = "Water Resources & Public Health"
        sdg_tag = "SDG 6: Clean Water & Sanitation"
        ai_tech_stack = "Acoustic Hydrophones, Flow Sensors, LoRaWAN, Edge AI"
        ai_recommended_depts = "Civil Engineering, Environmental Engineering, IoT & Embedded Systems"
    elif any(w in combined for w in ["waste", "garbage", "trash", "dump", "plastic", "kachra", "recycl", "compost"]):
        category = "Waste Management & Circular Economy"
        department = "Sanitation & Waste Management"
        sdg_tag = "SDG 12: Responsible Consumption & Production"
        ai_tech_stack = "Computer Vision Waste Sorting, Automated Anaerobic Digester, GPS RFID Bins"
        ai_recommended_depts = "Biotechnology, Chemical Engineering, Computer Vision"
    elif any(w in combined for w in ["road", "pothole", "traffic", "accident", "bus", "transport", "signal", "mobility"]):
        category = "Smart Mobility & Transport"
        department = "Roads & Transportation"
        sdg_tag = "SDG 11: Sustainable Cities & Communities"
        ai_tech_stack = "YOLOv8 Object Detection, Edge Dashcam, GIS Spatial Mapping"
        ai_recommended_depts = "Computer Science, Transportation Engineering, Geoinformatics"
    elif any(w in combined for w in ["solar", "energy", "electricity", "power", "grid", "light", "bijli", "carbon"]):
        category = "Clean Energy & Climate"
        department = "Renewable Energy & Electrical Dept"
        sdg_tag = "SDG 7: Affordable & Clean Energy"
        ai_tech_stack = "Microgrid Inverters, IoT Smart Metering, Solar MPPT Controllers"
        ai_recommended_depts = "Electrical Engineering, Energy Studies, Materials Science"
    elif any(w in combined for w in ["farmer", "crop", "harvest", "storage", "mandi", "agriculture", "irrigation", "soil"]):
        category = "Rural & Agricultural Tech"
        department = "Agriculture & Rural Development"
        sdg_tag = "SDG 2: Zero Hunger & Rural Innovation"
        ai_tech_stack = "Phase Change Material (PCM) Thermal Storage, Soil NPK Sensors, Satellite Remote Sensing"
        ai_recommended_depts = "Agricultural Engineering, Thermal Science, AI/ML"
    elif any(w in combined for w in ["health", "hospital", "clinic", "disease", "hygiene", "mosquito", "dengue", "medical"]):
        category = "Healthcare & Community Health"
        department = "Public Health & Medical Services"
        sdg_tag = "SDG 3: Good Health & Well-Being"
        ai_tech_stack = "Point-of-Care Diagnostics, Vector Heatmap Analytics, Tele-medicine Portal"
        ai_recommended_depts = "Biomedical Engineering, Public Health, Data Science"

    if any(w in combined for w in ["urgent", "danger", "hazard", "fatal", "emergency", "severe", "khata", "crisis"]):
        priority = "High"
    elif any(w in combined for w in ["minor", "low", "cosmetic", "survey"]):
        priority = "Low"

    # Groq AI enhancement
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if GROQ_AVAILABLE and groq_key:
        try:
            client = Groq(api_key=groq_key)
            prompt = f"""You are an AI civic innovation architect for NagrikSnap (Collaborative Civic & Societal Innovation Platform).
Analyze this crowdsourced societal problem and return ONLY a JSON object with these exact keys:
{{
  "title": "Clear concise 5-8 word technical challenge title",
  "department": "Government Department name",
  "category": "One of: Water & Sanitation, Waste Management & Circular Economy, Smart Mobility & Transport, Clean Energy & Climate, Rural & Agricultural Tech, Healthcare & Community Health, Civic Infrastructure",
  "sdg_tag": "Relevant UN SDG e.g. SDG 6: Clean Water, SDG 11: Sustainable Cities, SDG 7: Clean Energy, etc.",
  "priority": "High, Medium, or Low",
  "ai_tech_stack": "Recommended hardware, AI models, software stack (comma-separated)",
  "ai_recommended_depts": "Target university engineering/research departments (comma-separated)",
  "ai_summary": "2-sentence technical problem & solution brief for university student teams"
}}

Problem Title/Description: {title} - {text}"""

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300,
            )
            import re
            content = response.choices[0].message.content
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                res = json.loads(match.group())
                title = res.get("title", title)
                department = res.get("department", department)
                category = res.get("category", category)
                sdg_tag = res.get("sdg_tag", sdg_tag)
                priority = res.get("priority", priority)
                ai_tech_stack = res.get("ai_tech_stack", ai_tech_stack)
                ai_recommended_depts = res.get("ai_recommended_depts", ai_recommended_depts)
                ai_summary = res.get("ai_summary", ai_summary)
        except Exception as e:
            print(f"[Groq AI Error] {e}")

    return {
        "title": title or (text[:50] + "..."),
        "department": department,
        "category": category,
        "sdg_tag": sdg_tag,
        "priority": priority,
        "ai_tech_stack": ai_tech_stack,
        "ai_recommended_depts": ai_recommended_depts,
        "ai_summary": ai_summary
    }


def generate_challenge_id():
    return f"CH-2026-{uuid.uuid4().hex[:6].upper()}"


# ===== Models =====
class ChatMessageRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None
    language: Optional[str] = "en"


class LoginRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = None


class RegisterRequest(BaseModel):
    name: str
    phone: str
    email: str
    # role is deliberately ignored; public registration always creates citizens.
    role: Optional[str] = None
    organization: Optional[str] = ""
    department: Optional[str] = ""
    password: Optional[str] = ""


class StatusUpdate(BaseModel):
    status: str
    assigned_team_id: Optional[str] = None
    assigned_team_name: Optional[str] = None
    assigned_university: Optional[str] = None
    bounty_amount: Optional[float] = None


class ProposalSubmit(BaseModel):
    challenge_id: str
    team_name: str
    university_name: str
    lead_name: str
    lead_email: str
    lead_phone: Optional[str] = ""
    faculty_mentor: Optional[str] = ""
    tech_stack: Optional[str] = ""
    abstract: str
    github_url: Optional[str] = ""
    demo_url: Optional[str] = ""
    budget_needed: Optional[float] = 0.0


class SponsorshipSubmit(BaseModel):
    challenge_id: str
    company_name: str
    contact_name: str
    contact_email: str
    csr_domain: Optional[str] = ""
    pledge_amount: float
    resources_offered: Optional[str] = ""
    mentor_name: Optional[str] = ""


class CaseRoomMessageSubmit(BaseModel):
    challenge_id: str
    sender_name: str
    sender_role: str # govt, university, industry, citizen
    sender_org: Optional[str] = ""
    message: str
    attachment_url: Optional[str] = ""


class MilestoneSubmit(BaseModel):
    challenge_id: str
    title: str
    description: Optional[str] = ""
    progress_percent: int = 0
    status: Optional[str] = "pending"
    proof_url: Optional[str] = ""


class MilestoneReviewSubmit(BaseModel):
    decision: str
    note: Optional[str] = ""


class CollaborationInviteSubmit(BaseModel):
    user_id: str
    member_role: str = "member"


class CollaborationInviteDecision(BaseModel):
    decision: str


class CollaborationTaskSubmit(BaseModel):
    title: str
    description: Optional[str] = ""
    assigned_to: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[str] = ""


class CollaborationTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None


class ReviewSubmit(BaseModel):
    complaint_id: str
    rating: int
    comment: Optional[str] = ""
    name: Optional[str] = "Citizen"
    phone: Optional[str] = ""
    department: Optional[str] = ""
    impact_score: Optional[int] = 5


class OrganizationVerificationSubmit(BaseModel):
    requested_role: str
    organization_name: str
    department: Optional[str] = ""
    contact_email: str
    website: Optional[str] = ""
    justification: str


class OrganizationVerificationReview(BaseModel):
    decision: str
    note: Optional[str] = ""


class UniversityProfileSubmit(BaseModel):
    expertise: str
    sdg_focus: Optional[str] = ""
    past_projects: int = 0
    available_slots: int = 0
    districts: Optional[str] = ""
    website: Optional[str] = ""


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


# ===== Email delivery (SMTP; real delivery requires deployment configuration) =====
def send_email(to_email: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender or not to_email:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
                server.starttls(); server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"[email] delivery failed ({type(exc).__name__})")
        return False


def send_login_notice(user: dict, request: Request):
    email = (user.get("email") or "").strip()
    if not email:
        return
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    ip = request.client.host if request and request.client else "unknown"
    send_email(email, "New sign-in to your NagrikSnap account",
               f"Hello {user.get('name','there')},\n\nA sign-in to your NagrikSnap account was recorded at {now}.\nIP address: {ip}\nIf this wasn't you, change your password and contact the administrator.\n\nNagrikSnap")


# ===== Authentication API =====
@app.post("/auth/login")
def login(data: LoginRequest, request: Request):
    username = (data.username or "").strip()
    password = data.password or ""

    # Optional environment-provisioned admin; never use a built-in default credential.
    if ADMIN_USERNAME and ADMIN_PASSWORD_HASH and username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD_HASH):
        token = create_token(username, "admin", "admin-default")
        return {
            "success": True,
            "token": token,
            "username": username,
            "name": "Central Municipal Administrator",
            "role": "admin",
            "organization": "Smart City Innovation Cell",
            "message": "Admin login successful"
        }

    users = db.get_users()
    match = next(
        (u for u in users
         if (u.get("name", "").lower() == username.lower()
             or (u.get("username") or "").lower() == username.lower()
             or (u.get("email") or "").lower() == username.lower()
             or str(u.get("phone", "")) == username)
         and verify_password(password, u.get("password_hash") or "")),
        None
    )
    if match:
        if match.get("password_hash", "").find("$argon2") != 0:
            try:
                db.update_user_password(match.get("id"), hash_password(password))
            except Exception:
                pass
        token = create_token(match.get("name") or username, match.get("role", "citizen"), match.get("id"))
        send_login_notice(match, request)
        return {
            "success": True,
            "token": token,
            "user_id": match.get("id"),
            "username": match.get("username") or username,
            "email": match.get("email", ""),
            "name": match.get("name"),
            "role": match.get("role", "citizen"),
            "organization": match.get("organization", ""),
            "department": match.get("department", ""),
            "message": "Login successful"
        }

    raise HTTPException(status_code=401, detail="Invalid username or password")


class DemoLoginRequest(BaseModel):
    role: str


@app.post("/auth/demo-login")
def demo_login(data: DemoLoginRequest):
    allow_demo = (APP_ENV == "development") or (os.getenv("ALLOW_DEMO_SIGNIN", "true").lower() in {"true", "1", "yes"})
    if not allow_demo:
        raise HTTPException(status_code=404, detail="Demo sign-in is available only in development.")

    demo_email_candidates = {
        "citizen": ["demo.citizen@example.test", "aman.2710.singh.1947@gmail.com"],
        "govt_admin": ["demo.government@example.test", "demo.govt@example.test"],
        "university": ["demo.university@example.test"],
        "industry": ["demo.industry@example.test"],
        "admin": ["demo.admin@example.test"],
        "super_admin": ["demo.admin@example.test"],
    }
    candidates = demo_email_candidates.get(data.role, [])
    user = None
    for email in candidates:
        candidate_user = db.get_user_by_email(email)
        if candidate_user and (candidate_user.get("role") == data.role or (data.role == "super_admin" and candidate_user.get("role") == "admin")):
            user = candidate_user
            break

    if not user:
        raise HTTPException(status_code=404, detail=f"This role's demo account is not provisioned.")

    token = create_token(user.get("name") or user["email"], user["role"], user.get("id"))
    return {
        "success": True,
        "token": token,
        "user_id": user.get("id"),
        "username": user.get("username") or user["email"],
        "email": user.get("email", ""),
        "name": user.get("name"),
        "role": user["role"],
        "organization": user.get("organization", ""),
        "department": user.get("department", ""),
        "message": "Demo login successful",
    }


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    reset_id: str
    otp: str
    new_password: str


@app.post("/auth/password-reset/request")
def request_password_reset(data: PasswordResetRequest):
    email = (data.email or "").strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Provide a valid email address")
    # Same response whether the address exists or not, to reduce account enumeration.
    user = db.get_user_by_email(email)
    if user and os.getenv("SMTP_HOST", "").strip() and os.getenv("SMTP_FROM", "").strip():
        otp = f"{secrets.randbelow(1000000):06d}"
        reset_id = uuid.uuid4().hex
        expires = (datetime.now() + timedelta(minutes=10)).isoformat()
        db.create_password_reset_token(reset_id, user["id"], hashlib.sha256(otp.encode()).hexdigest(), expires)
        if not send_email(email, "Your NagrikSnap password reset code", f"Your password reset OTP is {otp}. It expires in 10 minutes. If you didn't request this, ignore this email."):
            # Invalidate token if delivery did not succeed.
            db.increment_reset_attempt(reset_id)
            raise HTTPException(status_code=503, detail="Email delivery is temporarily unavailable. Try again later.")
        return {"success": True, "message": "If the account exists, a reset code has been sent to its registered email.", "reset_id": reset_id}
    return {"success": True, "message": "If the account exists, a reset code has been sent to its registered email."}


@app.post("/auth/password-reset/confirm")
def confirm_password_reset(data: PasswordResetConfirm):
    if len(data.new_password or "") < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters")
    if not re.fullmatch(r"[0-9]{6}", data.otp or ""):
        raise HTTPException(status_code=422, detail="Enter the 6-digit OTP")
    token = db.get_password_reset_token(data.reset_id)
    if not token or token.get("used_at") or token.get("expires_at", "") <= datetime.now().isoformat() or int(token.get("attempts", 0)) >= 5:
        raise HTTPException(status_code=400, detail="Reset code is invalid or expired. Request a new code.")
    if not hmac.compare_digest(token["token_hash"], hashlib.sha256(data.otp.encode()).hexdigest()):
        db.increment_reset_attempt(data.reset_id)
        raise HTTPException(status_code=400, detail="Reset code is invalid or expired. Request a new code.")
    if not db.consume_password_reset_token(data.reset_id, hash_password(data.new_password)):
        raise HTTPException(status_code=400, detail="Reset code is invalid or expired. Request a new code.")
    return {"success": True, "message": "Password reset successfully. Please sign in again."}


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:].strip()
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    db.revoke_session(hashlib.sha256(token.encode()).hexdigest())
    return {"success": True, "message": "Logged out"}


@app.post("/auth/logout-all")
def logout_all(request: Request, user=Depends(verify_token)):
    """Revoke every active session for the authenticated account."""
    user_id = str(user.get("user_id") or "")
    if not user_id:
        # Environment-provisioned administrator has a stable synthetic ID.
        user_id = "admin-default" if user.get("role") == "govt_admin" else ""
    if not user_id:
        raise HTTPException(status_code=400, detail="This account cannot revoke sessions by user ID")
    revoked = db.revoke_user_sessions(user_id)
    db.log_audit({
        "actor_id": user_id, "actor_name": user.get("username", ""),
        "actor_role": user.get("role", ""), "action": "logout_all_sessions",
        "resource_type": "auth_session", "resource_id": user_id,
        "ip_address": request.client.host if request and request.client else "",
    })
    return {"success": True, "revoked_sessions": revoked, "message": "All sessions revoked; sign in again."}


@app.post("/auth/register")
def register(data: RegisterRequest):
    if not data.password or len(data.password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters")
    email = (data.email or "").strip().lower()
    if not data.name.strip() or not re.fullmatch(r"[+0-9 ()-]{8,20}", data.phone.strip()):
        raise HTTPException(status_code=422, detail="Provide a name and valid phone number")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Provide a valid email address")
    if db.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    if any(str(u.get("phone", "")) == data.phone.strip() for u in db.get_users()):
        raise HTTPException(status_code=409, detail="An account with this phone number already exists")
    user_id = f"U-{uuid.uuid4().hex[:8].upper()}"
    pwd_hash = hash_password(data.password)
    user = {
        "id": user_id,
        "name": data.name,
        "username": data.name.lower().replace(" ", "_") + str(secrets.randbelow(100)),
        "phone": data.phone,
        "email": email,
        "password_hash": pwd_hash,
        "role": "citizen",
        # Self-declared organization data is not an authorization credential.
        "organization": "",
        "department": "",
        "address": "",
        "lat": None,
        "lng": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "last_login": datetime.now().isoformat(),
    }
    db.add_user(user)
    token = create_token(user["name"], user["role"], user_id)
    return {
        "success": True,
        "token": token,
        "user": {k: v for k, v in user.items() if k != "password_hash"},
        "message": f"Registered successfully as {user['role']}"
    }


# ===== Organization verification workflow (P1) =====
@app.post("/api/organization-verification")
def submit_organization_verification(data: OrganizationVerificationSubmit, request: Request, user=Depends(verify_token)):
    if user.get("role") != "citizen":
        raise HTTPException(status_code=403, detail="Only citizen accounts can request an organization role")
    role = (data.requested_role or "").strip().lower()
    if role not in {"university", "industry"}:
        raise HTTPException(status_code=422, detail="requested_role must be university or industry")
    org = (data.organization_name or "").strip()
    email = (data.contact_email or "").strip().lower()
    justification = (data.justification or "").strip()
    website = (data.website or "").strip()
    if not 2 <= len(org) <= 160 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Provide a valid organization name and contact email")
    if len(justification) < 20 or len(justification) > 2000:
        raise HTTPException(status_code=422, detail="Justification must be 20-2000 characters")
    if website and (len(website) > 255 or not re.fullmatch(r"https://[^\s]+", website, re.I)):
        raise HTTPException(status_code=422, detail="Website must be an HTTPS URL")
    record = {"id": f"OV-{uuid.uuid4().hex[:12].upper()}", "user_id": user.get("user_id"),
        "requested_role": role, "organization_name": org, "department": (data.department or "").strip()[:120],
        "contact_email": email, "website": website, "justification": justification,
        "created_at": datetime.now().isoformat()}
    try:
        saved = db.create_org_verification_request(record)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    audit_action(user, "organization_verification.submit", "organization_verification", record["id"], request)
    return {"success": True, "request": saved}


@app.get("/api/organization-verification/mine")
def my_organization_verification_requests(user=Depends(verify_token)):
    return {"requests": db.list_org_verification_requests(user_id=user.get("user_id"), limit=50)}


@app.get("/api/admin/organization-verification")
def list_organization_verification_requests(status: str = Query("pending", pattern="^(pending|approved|rejected|all)$"),
                                           limit: int = Query(100, ge=1, le=500),
                                           user=Depends(require_roles("admin", "govt_admin"))):
    return {"requests": db.list_org_verification_requests(status=None if status == "all" else status, limit=limit)}


@app.post("/api/admin/organization-verification/{request_id}/review")
def review_organization_verification(request_id: str, data: OrganizationVerificationReview, request: Request,
                                     user=Depends(require_roles("admin", "govt_admin"))):
    decision = (data.decision or "").strip().lower()
    note = (data.note or "").strip()[:1000]
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="decision must be approved or rejected")
    if decision == "rejected" and len(note) < 5:
        raise HTTPException(status_code=422, detail="A rejection reason of at least 5 characters is required")
    try:
        reviewed = db.review_org_verification_request(request_id, user.get("user_id", "admin-default"), decision, note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not reviewed:
        raise HTTPException(status_code=404, detail="Verification request not found")
    audit_action(user, f"organization_verification.{decision}", "organization_verification", request_id, request)
    return {"success": True, "request": reviewed, "message": "Organization role updated" if decision == "approved" else "Request rejected"}


# ===== System Health Check (Production Readiness) =====
@app.get("/api/health")
@app.get("/health")
def health_check():
    db_status = "connected"
    engine = "sqlite"
    try:
        if getattr(db, "IS_POSTGRES", False):
            engine = "postgresql (neon cloud)"
        db.get_complaints(page=1, per_page=1)
    except Exception as e:
        db_status = f"unhealthy: {e}"

    storage_mode = getattr(evidence_storage, "STORAGE_MODE", "local")
    groq_ready = bool(GROQ_AVAILABLE and os.getenv("GROQ_API_KEY", "").strip())
    sms_provider = "twilio" if (os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")) else ("fast2sms" if os.getenv("FAST2SMS_API_KEY") else "simulated")

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "database": {"engine": engine, "status": db_status},
        "storage": {"mode": storage_mode},
        "ai": {"groq_llama_ready": groq_ready},
        "notifications": {"sms_provider": sms_provider}
    }


# ===== Societal Challenges Endpoints (PS 26043) =====
@app.get("/api/challenges")
@app.get("/complaints")
def list_challenges(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    sdg: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100)
):
    filters = {
        "status": status,
        "priority": priority,
        "department": department,
        "sdg": sdg,
        "category": category,
    }
    items, total = db.get_complaints(filters=filters, search=search, page=page, per_page=per_page)
    items = [{k: v for k, v in item.items() if k not in {"phone", "assigned_admin", "assigned_admin_id", "assigned_admin_name"}} for item in items]
    return {
        "challenges": items,
        "complaints": items, # backward compatibility
        "total": total,
        "page": page,
        "per_page": per_page
    }


@app.get("/api/challenges/{challenge_id}")
@app.get("/complaints/{challenge_id}")
def get_challenge(challenge_id: str):
    c = db.get_complaint_by_id(challenge_id)
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Public detail exposes only challenge fields. Collaboration records and personal
    # contact information are available only through authenticated endpoints.
    public_challenge = {k: v for k, v in c.items() if k not in {"phone", "assigned_admin", "assigned_admin_id", "assigned_admin_name"}}
    return public_challenge


@app.get("/api/me/complaints")
def list_my_complaints(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100), user=Depends(verify_token)):
    """Account-scoped complaint list; legacy anonymous reports are intentionally excluded."""
    if user.get("role") != "citizen" or not user.get("user_id"):
        raise HTTPException(status_code=403, detail="Citizen account required")
    items, total = db.get_complaints_by_owner(user["user_id"], page=page, per_page=per_page)
    safe_items = [{k: v for k, v in item.items() if k not in {"phone", "assigned_admin", "assigned_admin_id", "assigned_admin_name", "owner_user_id"}} for item in items]
    return {"complaints": safe_items, "total": total, "page": page, "per_page": per_page}


@app.get("/api/me/profile")
def get_my_profile(user=Depends(verify_token)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not in session")
    u = db.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User profile not found")
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "username": u.get("username"),
        "email": u.get("email"),
        "phone": u.get("phone"),
        "address": u.get("address", ""),
        "role": u.get("role"),
        "created_at": u.get("created_at")
    }


@app.put("/api/me/profile")
@app.post("/api/me/profile")
def update_my_profile(data: ProfileUpdateRequest, user=Depends(verify_token)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not in session")
    u = db.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User profile not found")

    new_name = (data.name or u.get("name") or "").strip()
    new_email = (data.email or u.get("email") or "").strip().lower()
    new_phone = (data.phone or u.get("phone") or "").strip()
    new_address = (data.address if data.address is not None else u.get("address", "")).strip()

    if not new_name:
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    if new_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", new_email):
        raise HTTPException(status_code=422, detail="Provide a valid email address")

    existing = db.get_user_by_email(new_email)
    if existing and existing.get("id") != user_id:
        raise HTTPException(status_code=409, detail="This email is already in use by another account")

    updated = db.update_user_profile(user_id, new_name, new_email, new_phone, new_address)
    token = create_token(new_name, u.get("role", "citizen"), user_id)
    return {
        "success": True,
        "message": "Profile updated successfully",
        "token": token,
        "user": {
            "id": updated.get("id"),
            "name": updated.get("name"),
            "username": updated.get("username"),
            "email": updated.get("email"),
            "phone": updated.get("phone"),
            "address": updated.get("address"),
            "role": updated.get("role")
        }
    }


@app.post("/api/challenges")
@app.post("/complaints")
async def create_challenge(
    title: Optional[str] = Form(None),
    description: str = Form(...),
    phone: str = Form(...),
    address: Optional[str] = Form(None),
    district: Optional[str] = Form(None),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    department: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    sdg_tag: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    bounty_amount: Optional[float] = Form(0.0),
    photo: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None)
):
    submitting_user = None
    if authorization:
        submitting_user = verify_token(authorization=authorization)
        if submitting_user.get("role") != "citizen" or not submitting_user.get("user_id"):
            raise HTTPException(status_code=403, detail="Only a signed-in citizen can link a report to their account")
    if not description.strip() or len(description) > 10000 or not re.fullmatch(r"[+0-9 ()-]{8,20}", phone.strip()):
        raise HTTPException(status_code=422, detail="Description is required (max 10000 characters) and phone must be valid")
    if lat is not None and not -90 <= lat <= 90 or lng is not None and not -180 <= lng <= 180:
        raise HTTPException(status_code=422, detail="Invalid latitude or longitude")
    if title and len(title) > 200:
        raise HTTPException(status_code=422, detail="Title must be at most 200 characters")
    if bounty_amount is not None and (not math.isfinite(bounty_amount) or bounty_amount < 0 or bounty_amount > 100000000):
        raise HTTPException(status_code=422, detail="Invalid bounty amount")
    cid = generate_challenge_id()
    photo_path = ""
    if photo and photo.filename:
        if photo.content_type not in ALLOWED_UPLOAD_TYPES:
            raise HTTPException(status_code=415, detail="Only JPEG, PNG, and WebP images are accepted")
        content = await photo.read(MAX_UPLOAD_BYTES + 1)
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"Image must be between 1 byte and {MAX_UPLOAD_BYTES} bytes")
        # Validate common file signatures; do not trust filename or MIME type alone.
        signatures = {"image/jpeg": content.startswith(b"\xff\xd8\xff"),
                      "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
                      "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"}
        if not signatures.get(photo.content_type, False):
            raise HTTPException(status_code=415, detail="Image content does not match its declared type")
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[photo.content_type]
        fn = f"{cid}_{uuid.uuid4().hex}{ext}"
        try:
            storage_key = evidence_storage.save_evidence(fn, content, photo.content_type)
        except Exception:
            raise HTTPException(status_code=503, detail="Evidence storage is temporarily unavailable")
        photo_path = f"/uploads/{storage_key}"

    # AI classification & SDG matchmaking
    ai_meta = classify_societal_challenge(description, title or "")

    nearest = find_nearest_admin(lat, lng, department or ai_meta["department"])

    challenge_record = {
        "id": cid,
        "owner_user_id": submitting_user.get("user_id") if submitting_user else None,
        "title": title or ai_meta["title"],
        "description": description,
        "phone": phone,
        "address": address or "Location captured via GPS",
        "district": (district or "").strip()[:100],
        "lat": lat,
        "lng": lng,
        "department": department or ai_meta["department"],
        "category": category or ai_meta["category"],
        "sdg_tag": sdg_tag or ai_meta["sdg_tag"],
        "priority": priority or ai_meta["priority"],
        "status": "Crowdsourced",
        "photo": photo_path,
        "bounty_amount": bounty_amount or 0.0,
        "assigned_admin": nearest,
        "assigned_admin_id": nearest["admin_id"] if nearest else None,
        "assigned_admin_name": nearest["admin_name"] if nearest else None,
        "assigned_team_id": None,
        "assigned_team_name": None,
        "assigned_university": None,
        "sponsor_id": None,
        "sponsor_name": None,
        "sponsor_grant": 0.0,
        "ai_tech_stack": ai_meta["ai_tech_stack"],
        "ai_recommended_depts": ai_meta["ai_recommended_depts"],
        "ai_summary": ai_meta["ai_summary"],
        "created_at": datetime.now().isoformat(),
    }

    db.add_complaint(challenge_record)

    # Send citizen acknowledgement SMS
    sms_msg = f"SamadhanSetu: Your challenge has been logged! ID: {cid}. Track: http://localhost:8000/track.html?id={cid}"
    send_sms(phone, sms_msg)

    return {
        "success": True,
        "challenge_id": cid,
        "tracking_id": cid,
        "challenge": {k: v for k, v in challenge_record.items() if k not in {"phone", "assigned_admin", "assigned_admin_id", "assigned_admin_name"}},
        "ai_insights": ai_meta,
        "message": "Societal challenge published successfully!"
    }


@app.get("/api/challenges/{challenge_id}/status-history")
def get_challenge_status_history(challenge_id: str):
    """Return status-only history for a known tracking ID; excludes actor identity and private contact data."""
    if not db.get_complaint_by_id(challenge_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    return {"challenge_id": challenge_id, "history": db.get_complaint_status_history(challenge_id)}


@app.put("/api/challenges/{challenge_id}/status")
@app.put("/complaints/{challenge_id}/status")
def update_challenge_status(challenge_id: str, data: StatusUpdate, request: Request, user=Depends(require_roles("admin", "govt_admin"))):
    c = db.get_complaint_by_id(challenge_id)
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    allowed_statuses = {"Crowdsourced", "Under Review", "Verified", "Assigned", "In Progress", "Pilot", "Resolved", "Rejected"}
    if data.status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Invalid challenge status")
    recorded_milestones = db.get_milestones(challenge_id)
    if data.status in {"Pilot", "Resolved"} and recorded_milestones:
        approved = [m for m in recorded_milestones if m.get("review_decision") == "approved"]
        if not approved:
            raise HTTPException(status_code=409, detail="At least one milestone must be approved by government before moving this challenge to Pilot or Resolved")
        if data.status == "Resolved" and not any(int(m.get("progress_percent") or 0) == 100 and m.get("review_decision") == "approved" for m in approved):
            raise HTTPException(status_code=409, detail="A 100% milestone must be approved before resolving this challenge")
    fields = {"status": data.status}
    if data.assigned_team_id:
        fields["assigned_team_id"] = data.assigned_team_id
    if data.assigned_team_name:
        fields["assigned_team_name"] = data.assigned_team_name
    if data.assigned_university:
        fields["assigned_university"] = data.assigned_university
    if data.bounty_amount is not None:
        fields["bounty_amount"] = data.bounty_amount

    result = db.update_complaint_status_atomic(
        challenge_id, fields,
        actor_user_id=user.get("user_id", ""),
        actor_name=user.get("name") or user.get("username", "Government reviewer"),
        actor_role=user.get("role", ""),
        note="Status updated by an authorized reviewer",
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    audit_action(user, "challenge.status.update", "challenge", challenge_id, request)

    # Notification delivery is handled asynchronously by the outbox worker.
    # The intent is written atomically with the status/history transition.

    return {"success": True, "challenge_id": challenge_id, "status": data.status}


# ===== University Proposals & Bidding Endpoints =====
@app.get("/api/challenges/{challenge_id}/proposals")
def get_challenge_proposals(challenge_id: str, user=Depends(require_case_member)):
    if not db.get_complaint_by_id(challenge_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=403, detail="You are not authorized to view proposals for this challenge")
    proposals = db.get_proposals(challenge_id)
    if user.get("role") not in {"admin", "govt_admin"}:
        proposals = [{k:v for k,v in p.items() if k not in {"lead_email", "lead_phone"}} for p in proposals]
    return {"proposals": proposals}


@app.get("/api/me/proposals")
def list_my_proposals(user=Depends(require_roles("university"))):
    return {"proposals": db.get_user_proposals(user.get("user_id", ""))}


@app.get("/api/proposals")
def list_all_proposals(user=Depends(require_roles("admin", "govt_admin"))):
    return {"proposals": db.get_proposals()}


@app.post("/api/challenges/{challenge_id}/proposals")
def submit_university_proposal(challenge_id: str, data: ProposalSubmit, user=Depends(require_roles("university", "admin", "govt_admin"))):
    c = db.get_complaint_by_id(challenge_id)
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if user.get("role") == "university":
        org = str(user.get("organization") or "").strip().casefold()
        if not org or str(data.university_name or "").strip().casefold() != org:
            raise HTTPException(status_code=403, detail="University name must match your verified account organization")
    prop_id = f"PROP-{uuid.uuid4().hex[:6].upper()}"
    prop_record = {
        "id": prop_id,
        "challenge_id": challenge_id,
        "team_name": data.team_name,
        "university_name": data.university_name,
        "lead_name": data.lead_name,
        "lead_email": data.lead_email,
        "lead_phone": data.lead_phone or "",
        "faculty_mentor": data.faculty_mentor or "",
        "tech_stack": data.tech_stack or "",
        "abstract": data.abstract,
        "github_url": data.github_url or "",
        "demo_url": data.demo_url or "",
        "budget_needed": data.budget_needed or 0.0,
        "status": "submitted",
        "created_at": datetime.now().isoformat(),
        "submitted_by_user_id": user.get("user_id", "")
    }
    db.add_proposal(prop_record)

    # Add initial case room announcement
    db.add_case_room_message({
        "id": f"MSG-{uuid.uuid4().hex[:6].upper()}",
        "challenge_id": challenge_id,
        "sender_name": f"{data.lead_name} (Team Lead)",
        "sender_role": "university",
        "sender_org": data.university_name,
        "message": f"Proposal submitted by team '{data.team_name}'. Solution approach: {data.abstract[:180]}...",
        "attachment_url": "",
        "created_at": datetime.now().isoformat()
    })

    return {"success": True, "proposal_id": prop_id, "proposal": prop_record, "message": "Proposal submitted to Govt Innovation Review Board!"}


@app.post("/api/proposals/{proposal_id}/accept")
def accept_proposal_endpoint(proposal_id: str, request: Request, user=Depends(require_roles("admin", "govt_admin"))):
    res = db.accept_proposal(proposal_id)
    if not res:
        raise HTTPException(status_code=404, detail="Proposal not found")
    audit_action(user, "proposal.accept", "proposal", proposal_id, request)
    
    # Announce in case room
    db.add_case_room_message({
        "id": f"MSG-{uuid.uuid4().hex[:6].upper()}",
        "challenge_id": res["challenge_id"],
        "sender_name": "Govt Innovation Cell",
        "sender_role": "govt",
        "sender_org": "Municipal Review Board",
        "message": f"🎉 Congratulations! Team '{res['team_name']}' from '{res['university_name']}' has been officially selected to build and pilot this solution!",
        "attachment_url": "",
        "created_at": datetime.now().isoformat()
    })

    safe_result = {k: v for k, v in res.items() if k not in {"lead_email", "lead_phone"}}
    return {"success": True, "proposal": safe_result, "message": f"Proposal accepted. Team {res['team_name']} assigned to challenge."}


# ===== Industry / CSR Sponsorship Endpoints =====
@app.get("/api/challenges/{challenge_id}/sponsorships")
def get_challenge_sponsorships(challenge_id: str, user=Depends(require_case_member)):
    if not db.get_complaint_by_id(challenge_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=403, detail="You are not authorized to view sponsorships for this challenge")
    records = db.get_sponsorships(challenge_id)
    if user.get("role") not in {"admin", "govt_admin"}:
        records = [{k:v for k,v in x.items() if k not in {"contact_email", "contact_name"}} for x in records]
    return {"sponsorships": records}


@app.get("/api/me/sponsorships")
def list_my_sponsorships(user=Depends(require_roles("industry"))):
    return {"sponsorships": db.get_user_sponsorships(user.get("user_id", ""))}


@app.get("/api/sponsorships")
def list_all_sponsorships(user=Depends(require_roles("admin", "govt_admin"))):
    return {"sponsorships": db.get_sponsorships()}


@app.post("/api/challenges/{challenge_id}/sponsor")
@app.post("/api/challenges/{challenge_id}/sponsorships")
def pledge_sponsorship(challenge_id: str, data: SponsorshipSubmit, request: Request, user=Depends(require_roles("industry", "admin", "govt_admin"))):
    c = db.get_complaint_by_id(challenge_id)
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if user.get("role") == "industry":
        org = str(user.get("organization") or "").strip().casefold()
        if not org or str(data.company_name or "").strip().casefold() != org:
            raise HTTPException(status_code=403, detail="Company name must match your verified account organization")
    spon_id = f"SPON-{uuid.uuid4().hex[:6].upper()}"
    spon_record = {
        "id": spon_id,
        "challenge_id": challenge_id,
        "company_name": data.company_name,
        "contact_name": data.contact_name,
        "contact_email": data.contact_email,
        "csr_domain": data.csr_domain or "",
        "pledge_amount": data.pledge_amount,
        "resources_offered": data.resources_offered or "",
        "mentor_name": data.mentor_name or "",
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "submitted_by_user_id": user.get("user_id", "")
    }
    db.add_sponsorship(spon_record)
    audit_action(user, "sponsorship.create", "challenge", challenge_id, request)

    # Announce in Case Room
    db.add_case_room_message({
        "id": f"MSG-{uuid.uuid4().hex[:6].upper()}",
        "challenge_id": challenge_id,
        "sender_name": data.contact_name,
        "sender_role": "industry",
        "sender_org": data.company_name,
        "message": f"🏢 CSR Grant Pledged: ₹{data.pledge_amount:,.0f} by {data.company_name}. Resources: {data.resources_offered or 'Tech Mentorship & Cloud Credits'}.",
        "attachment_url": "",
        "created_at": datetime.now().isoformat()
    })

    return {"success": True, "sponsorship_id": spon_id, "sponsorship": spon_record, "message": "CSR sponsorship registered!"}


# ===== Case Room Collaboration Workspace =====
@app.get("/api/challenges/{challenge_id}/case-room")
def get_case_room(challenge_id: str, user=Depends(require_case_member)):
    c = db.get_complaint_by_id(challenge_id)
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=403, detail="You are not a member of this case room")
    safe_challenge = {k: v for k, v in c.items() if k not in {"phone", "assigned_admin", "assigned_admin_id", "assigned_admin_name"}}
    proposals = db.get_proposals(challenge_id)
    sponsorships = db.get_sponsorships(challenge_id)
    if user.get("role") not in {"admin", "govt_admin"}:
        proposals = [{k: v for k, v in p.items() if k not in {"lead_email", "lead_phone"}} for p in proposals]
        sponsorships = [{k: v for k, v in x.items() if k not in {"contact_email", "contact_name"}} for x in sponsorships]
    return {
        "challenge": safe_challenge,
        "messages": db.get_case_room_messages(challenge_id),
        "milestones": db.get_milestones(challenge_id),
        "proposals": proposals,
        "sponsorships": sponsorships
    }


@app.post("/api/challenges/{challenge_id}/case-room")
def post_case_room_message(challenge_id: str, data: CaseRoomMessageSubmit, request: Request, user=Depends(require_case_member)):
    if not db.get_complaint_by_id(challenge_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=403, detail="You are not a member of this case room")
    msg_id = f"MSG-{uuid.uuid4().hex[:6].upper()}"
    msg_record = {
        "id": msg_id,
        "challenge_id": challenge_id,
        "sender_name": user.get("username") or "Authenticated user",
        "sender_role": user.get("role", ""),
        "sender_org": "",
        "message": data.message[:5000],
        "attachment_url": "",
        "created_at": datetime.now().isoformat()
    }
    db.add_case_room_message(msg_record)
    audit_action(user, "case_room.message.create", "challenge", challenge_id, request)
    return {"success": True, "message_id": msg_id, "message": msg_record}


# ===== Milestones & Pilot Deployment =====
@app.get("/api/challenges/{challenge_id}/milestones")
def get_milestones(challenge_id: str, user=Depends(require_case_member)):
    if not db.get_complaint_by_id(challenge_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=403, detail="You are not authorized to view milestones")
    return {"milestones": db.get_milestones(challenge_id)}


@app.post("/api/challenges/{challenge_id}/milestones")
def create_milestone(challenge_id: str, data: MilestoneSubmit, request: Request, user=Depends(require_roles("admin", "govt_admin", "university", "industry"))):
    if not db.get_complaint_by_id(challenge_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=403, detail="You are not authorized to create milestones")
    if not data.title or not data.title.strip():
        raise HTTPException(status_code=422, detail="Milestone title is required")
    if not 0 <= data.progress_percent <= 100:
        raise HTTPException(status_code=422, detail="Progress must be between 0 and 100")
    proof_url = (data.proof_url or "").strip()
    if proof_url and not re.match(r"^https?://[^\s]+$", proof_url, flags=re.IGNORECASE):
        raise HTTPException(status_code=422, detail="Evidence URL must use http:// or https://")
    ms_id = f"MS-{uuid.uuid4().hex[:6].upper()}"
    if data.status not in {"pending", "in_progress", "completed", "blocked"}:
        raise HTTPException(status_code=422, detail="Invalid milestone status")
    ms_record = {
        "id": ms_id,
        "challenge_id": challenge_id,
        "title": data.title,
        "description": data.description or "",
        "progress_percent": data.progress_percent,
        "status": data.status or "pending",
        "proof_url": proof_url,
        "review_decision": "pending_review",
        "review_note": "",
        "reviewer_user_id": "",
        "reviewer_name": "",
        "reviewer_role": "",
        "reviewed_at": "",
        "created_at": datetime.now().isoformat()
    }
    db.add_milestone(ms_record)
    audit_action(user, "milestone.create", "challenge", challenge_id, request)
    return {"success": True, "milestone_id": ms_id, "milestone": ms_record}




@app.put("/api/challenges/{challenge_id}/milestones/{milestone_id}/review")
def review_milestone(challenge_id: str, milestone_id: str, data: MilestoneReviewSubmit, request: Request,
                     user=Depends(require_roles("admin", "govt_admin"))):
    if not db.get_complaint_by_id(challenge_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    milestone = db.get_milestone_by_id(milestone_id)
    if not milestone or milestone.get("challenge_id") != challenge_id:
        raise HTTPException(status_code=404, detail="Milestone not found for this challenge")
    decision = (data.decision or "").strip().lower()
    if decision not in {"approved", "rejected", "needs_revision"}:
        raise HTTPException(status_code=422, detail="Decision must be approved, rejected, or needs_revision")
    note = (data.note or "").strip()[:2000]
    if decision != "approved" and not note:
        raise HTTPException(status_code=422, detail="A review note is required when rejecting or requesting revision")
    reviewed = db.review_milestone(milestone_id, decision, note, user)
    audit_action(user, f"milestone.review.{decision}", "milestone", milestone_id, request)
    return {"success": True, "milestone": reviewed}


# ===== P3: Team collaboration, invitations, and task tracking =====
def _require_challenge(challenge_id: str):
    challenge = db.get_complaint_by_id(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge


def _require_accepted_member(challenge_id: str, user: dict):
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=403, detail="You must be an authorized case-room member")


@app.get("/api/challenges/{challenge_id}/collaboration/members")
def list_collaboration_members(challenge_id: str, user=Depends(require_case_member)):
    _require_challenge(challenge_id)
    _require_accepted_member(challenge_id, user)
    members = db.list_collaboration_members(challenge_id)
    # Only admins see invite audit actor IDs; public user identifiers are limited to collaborators.
    return {"members": members}


@app.get("/api/challenges/{challenge_id}/collaboration/directory")
def search_collaboration_directory(challenge_id: str, q: str = "", user=Depends(require_case_member)):
    """Search a minimal user directory; only accepted project members can search it."""
    _require_challenge(challenge_id)
    _require_accepted_member(challenge_id, user)
    if user.get("role") not in {"admin", "govt_admin", "university"}:
        raise HTTPException(status_code=403, detail="Only government reviewers or university collaborators can search the directory")
    query = q.strip()
    if len(query) < 2:
        return {"users": [], "message": "Enter at least 2 characters to search."}
    users = db.search_collaboration_users(query, user.get("user_id", ""), 20)
    existing = {m.get("user_id") for m in db.list_collaboration_members(challenge_id)}
    # Avoid duplicate invitations/members. Never return phone, email, address or credential fields.
    users = [u for u in users if u.get("id") not in existing]
    return {"users": users}


@app.post("/api/challenges/{challenge_id}/collaboration/invitations")
def invite_collaborator(challenge_id: str, data: CollaborationInviteSubmit, request: Request,
                        user=Depends(require_case_member)):
    _require_challenge(challenge_id)
    _require_accepted_member(challenge_id, user)
    if user.get("role") not in {"admin", "govt_admin", "university"}:
        raise HTTPException(status_code=403, detail="Only government reviewers or university collaborators can invite team members")
    if data.member_role not in {"student", "faculty", "mentor", "member"}:
        raise HTTPException(status_code=422, detail="Invalid collaboration role")
    target = db.get_user_by_id(data.user_id.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User account not found")
    if target.get("role") in {"admin", "govt_admin"}:
        raise HTTPException(status_code=422, detail="Government accounts cannot be added as project team members")
    now = datetime.now().isoformat()
    record = db.upsert_collaboration_member({"id": f"MEM-{uuid.uuid4().hex[:10].upper()}",
        "challenge_id": challenge_id, "user_id": target["id"], "member_role": data.member_role,
        "status": "invited", "invited_by": user.get("user_id", ""), "created_at": now, "updated_at": now})
    audit_action(user, "collaboration.member.invite", "challenge", challenge_id, request)
    return {"success": True, "invitation": record, "message": "Invitation created; the invited user must accept it."}


@app.get("/api/collaboration/invitations/mine")
def my_collaboration_invitations(user=Depends(verify_token)):
    # Use the current user's membership records only; do not expose other users' invitations.
    memberships = db.list_user_collaboration_members(user.get("user_id", ""))
    return {"invitations": memberships}


@app.post("/api/challenges/{challenge_id}/collaboration/invitations/decision")
def decide_collaboration_invitation(challenge_id: str, data: CollaborationInviteDecision, request: Request,
                                   user=Depends(verify_token)):
    if data.decision not in {"accept", "decline"}:
        raise HTTPException(status_code=422, detail="Decision must be accept or decline")
    membership = db.get_collaboration_member(challenge_id, user.get("user_id", ""))
    if not membership or membership.get("status") != "invited":
        raise HTTPException(status_code=404, detail="Pending invitation not found")
    status = "accepted" if data.decision == "accept" else "declined"
    db.update_collaboration_member(challenge_id, user.get("user_id", ""), status, datetime.now().isoformat())
    audit_action(user, f"collaboration.invitation.{status}", "challenge", challenge_id, request)
    return {"success": True, "status": status}


@app.get("/api/challenges/{challenge_id}/collaboration/tasks")
def list_collaboration_tasks(challenge_id: str, user=Depends(require_case_member)):
    _require_challenge(challenge_id)
    _require_accepted_member(challenge_id, user)
    return {"tasks": db.list_collaboration_tasks(challenge_id)}


@app.post("/api/challenges/{challenge_id}/collaboration/tasks")
def create_collaboration_task(challenge_id: str, data: CollaborationTaskSubmit, request: Request,
                              user=Depends(require_case_member)):
    _require_challenge(challenge_id)
    _require_accepted_member(challenge_id, user)
    title = data.title.strip()
    if not title or len(title) > 160:
        raise HTTPException(status_code=422, detail="Task title must contain 1–160 characters")
    if data.priority not in {"low", "medium", "high"}:
        raise HTTPException(status_code=422, detail="Invalid task priority")
    if data.assigned_to:
        assignee = db.get_collaboration_member(challenge_id, data.assigned_to)
        if not assignee or assignee.get("status") != "accepted":
            raise HTTPException(status_code=422, detail="Assignee must be an accepted project member")
    now = datetime.now().isoformat()
    record = db.add_collaboration_task({"id": f"TASK-{uuid.uuid4().hex[:10].upper()}",
        "challenge_id": challenge_id, "title": title, "description": (data.description or "")[:3000],
        "assigned_to": data.assigned_to, "created_by": user.get("user_id", ""), "status": "todo",
        "priority": data.priority, "due_date": (data.due_date or "")[:40], "created_at": now, "updated_at": now})
    audit_action(user, "collaboration.task.create", "task", record["id"], request)
    return {"success": True, "task": record}


@app.patch("/api/collaboration/tasks/{task_id}")
def update_collaboration_task_endpoint(task_id: str, data: CollaborationTaskUpdate, request: Request,
                                      user=Depends(require_case_member)):
    task = db.get_collaboration_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _require_challenge(task["challenge_id"])
    _require_accepted_member(task["challenge_id"], user)
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        return {"success": True, "task": task}
    if "title" in fields:
        fields["title"] = fields["title"].strip()
        if not fields["title"] or len(fields["title"]) > 160:
            raise HTTPException(status_code=422, detail="Task title must contain 1–160 characters")
    if "description" in fields:
        fields["description"] = fields["description"][:3000]
    if "status" in fields and fields["status"] not in {"todo", "in_progress", "blocked", "done"}:
        raise HTTPException(status_code=422, detail="Invalid task status")
    if "priority" in fields and fields["priority"] not in {"low", "medium", "high"}:
        raise HTTPException(status_code=422, detail="Invalid task priority")
    if "assigned_to" in fields and fields["assigned_to"]:
        assignee = db.get_collaboration_member(task["challenge_id"], fields["assigned_to"])
        if not assignee or assignee.get("status") != "accepted":
            raise HTTPException(status_code=422, detail="Assignee must be an accepted project member")
    # Members can update task status/details only for tasks they created or are assigned.
    is_admin = user.get("role") in {"admin", "govt_admin"}
    is_owner = task.get("created_by") == user.get("user_id")
    is_assignee = task.get("assigned_to") == user.get("user_id")
    if not (is_admin or is_owner or is_assignee):
        raise HTTPException(status_code=403, detail="Only the task creator, assignee, or government reviewer can update this task")
    updated = db.update_collaboration_task(task_id, fields, datetime.now().isoformat())
    audit_action(user, "collaboration.task.update", "task", task_id, request)
    return {"success": True, "task": updated}


# ===== Reviews & Citizen Social Impact Score =====
@app.get("/api/reviews")
@app.get("/reviews")
def list_reviews():
    revs = [{k: v for k, v in r.items() if k != "phone"} for r in db.get_reviews()]
    avg_rating = round(sum(r["rating"] for r in revs) / len(revs), 1) if revs else 5.0
    return {"reviews": revs, "average": avg_rating, "total": len(revs)}


@app.post("/api/reviews")
@app.post("/reviews")
def create_review(data: ReviewSubmit, user=Depends(verify_token)):
    if not 1 <= data.rating <= 5 or not 1 <= (data.impact_score or 5) <= 10:
        raise HTTPException(status_code=422, detail="Rating must be 1-5 and impact score 1-10")
    if not db.get_complaint_by_id(data.complaint_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    r_id = f"REV-{uuid.uuid4().hex[:6].upper()}"
    account = db.get_user_by_id(user.get("user_id")) if user.get("user_id") else None
    rev_record = {
        "id": r_id,
        "complaint_id": data.complaint_id,
        "rating": data.rating,
        "comment": data.comment or "",
        "name": (account or {}).get("name") or "Authenticated user",
        "phone": "",
        "department": (account or {}).get("department") or "",
        "impact_score": data.impact_score or 5,
        "created_at": datetime.now().isoformat()
    }
    db.add_review(rev_record)
    return {"success": True, "review": rev_record}


# ===== Analytics Endpoint (SIH 26043 Dashboard) =====
@app.get("/api/analytics")
@app.get("/analytics")
def get_analytics():
    return db.analytics()


# ===== P4 Government Impact Analytics (aggregate-only, role-protected) =====
@app.get("/api/admin/impact-analytics")
def get_impact_analytics(
    date_from: Optional[str] = Query(None, alias="date_from", max_length=10),
    date_to: Optional[str] = Query(None, alias="date_to", max_length=10),
    district: Optional[str] = Query(None, max_length=100),
    department: Optional[str] = Query(None, max_length=100),
    user=Depends(require_roles("admin", "govt_admin")),
):
    """Aggregate dashboard. Complaint metrics can be filtered; other totals are all-time."""
    for value in (date_from, date_to):
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=422, detail="Dates must use YYYY-MM-DD format")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    result = db.impact_analytics(date_from=date_from, date_to=date_to, district=district, department=department)
    audit_action(user, "analytics.impact.view", "analytics", "state", None)
    return result


# ===== AI Matchmaking & Testing Endpoint =====
@app.post("/api/ai-match")
def ai_match_simulation(payload: dict, user=Depends(verify_token)):
    text = payload.get("description", "")
    title = payload.get("title", "")
    return classify_societal_challenge(text, title)


@app.get("/api/university/profile")
def read_university_profile(user=Depends(require_roles("university"))):
    """Return the signed-in, approved university account's own matching profile."""
    profile = db.get_university_profile(user.get("user_id"))
    return {"profile": profile}


@app.put("/api/university/profile")
def save_university_profile(data: UniversityProfileSubmit, request: Request,
                            user=Depends(require_roles("university"))):
    """P2: verified university accounts maintain the expertise/capacity used for matching."""
    expertise = (data.expertise or "").strip()
    if not expertise or len(expertise) > 1200:
        raise HTTPException(status_code=422, detail="Expertise is required and must be at most 1200 characters.")
    if data.past_projects < 0 or data.past_projects > 10000:
        raise HTTPException(status_code=422, detail="past_projects must be between 0 and 10000.")
    if data.available_slots < 0 or data.available_slots > 500:
        raise HTTPException(status_code=422, detail="available_slots must be between 0 and 500.")
    organization = (user.get("organization") or "").strip()
    if not organization:
        raise HTTPException(status_code=403, detail="An approved organization is required.")
    db.upsert_university_profile({
        "user_id": user.get("user_id"), "organization_name": organization,
        "expertise": expertise, "sdg_focus": (data.sdg_focus or "")[:500],
        "past_projects": data.past_projects, "available_slots": data.available_slots,
        "districts": (data.districts or "")[:500], "website": (data.website or "")[:300],
        "updated_at": datetime.now().isoformat()
    })
    audit_action(user, "university_profile_updated", "university_profile", user.get("user_id", ""), request)
    return {"success": True, "profile": db.get_university_profile(user.get("user_id"))}


def _match_universities(challenge: dict):
    """Transparent deterministic ranking; recommendations are advisory, not automatic assignments."""
    challenge_text = " ".join(str(challenge.get(k) or "") for k in
        ("title", "description", "category", "department", "sdg_tag", "ai_tech_stack", "ai_recommended_depts")).casefold()
    stop = {"and", "the", "for", "with", "from", "that", "this", "into", "using", "system", "project", "solution"}
    tokens = {t for t in re.findall(r"[a-z0-9+#.-]{3,}", challenge_text) if t not in stop}
    results = []
    for profile in db.list_university_profiles():
        expertise_tokens = {t for t in re.findall(r"[a-z0-9+#.-]{3,}", (profile.get("expertise", "") + " " + profile.get("sdg_focus", "")).casefold()) if t not in stop}
        overlap = sorted(tokens & expertise_tokens)
        expertise_score = min(60.0, 60.0 * len(overlap) / max(1, min(8, len(tokens))))
        capacity_score = 20.0 if int(profile.get("available_slots") or 0) > 0 else 0.0
        experience_score = min(15.0, int(profile.get("past_projects") or 0) * 3.0)
        location_text = (profile.get("districts") or "").casefold()
        challenge_location = str(challenge.get("address") or "").casefold()
        location_score = 5.0 if location_text and any(x.strip() and x.strip() in challenge_location for x in location_text.split(",")) else 0.0
        score = round(min(100.0, expertise_score + capacity_score + experience_score + location_score), 1)
        reasons = []
        if overlap: reasons.append("Shared expertise terms: " + ", ".join(overlap[:6]))
        if capacity_score: reasons.append("Currently reports available project capacity")
        else: reasons.append("No available project slots reported")
        if experience_score: reasons.append(f"Prior project experience: {int(profile.get('past_projects') or 0)} projects")
        if location_score: reasons.append("District coverage matches the challenge location")
        results.append({"organization_name": profile["organization_name"], "score": score,
            "available_slots": int(profile.get("available_slots") or 0),
            "expertise": profile.get("expertise", ""), "reasons": reasons,
            "matched_terms": overlap, "updated_at": profile.get("updated_at")})
    return sorted(results, key=lambda x: (-x["score"], x["organization_name"].casefold()))


@app.get("/api/challenges/{challenge_id}/matches")
def get_university_matches(challenge_id: str, limit: int = Query(10, ge=1, le=50),
                           user=Depends(require_roles("admin", "govt_admin"))):
    challenge = db.get_complaint_by_id(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    matches = _match_universities(challenge)[:limit]
    return {"challenge_id": challenge_id, "matches": matches,
            "method": "Explainable keyword overlap (60) + reported capacity (20) + prior projects (15) + location (5)",
            "notice": "Advisory ranking only. Verify profiles and review proposals before assignment."}


@app.get("/api/admin/audit-logs")
def read_audit_logs(limit: int = Query(100, ge=1, le=500), user=Depends(require_roles("admin", "govt_admin"))):
    return {"logs": db.get_audit_logs(limit)}


# ===== Jan Sevak Live AI Assistant =====
@app.post("/api/ai/chat")
async def chat_with_ai(body: ChatMessageRequest):
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if GROQ_AVAILABLE and groq_key:
        try:
            client = Groq(api_key=groq_key)
            system_prompt = (
                "You are Jan Sevak (जन सेवक), the official AI assistant for NagrikSnap. "
                "NagrikSnap is a quadruple-helix civic technology platform connecting Citizens, Universities, Industry CSR, and Government. "
                "Citizens crowdsource societal and municipal challenges with photo/video evidence and GPS. "
                "Universities explore open challenges, build technical prototypes, and earn innovation credits. "
                "Industries sponsor high-impact university proposals using CSR grants aligned with UN SDGs. "
                "Government administrators and municipal departments verify, approve, and pilot deploy winning solutions on the ground. "
                "Be polite, empowering, concise, and structured. "
                "Answer fluently in whichever language the user asks (English, Hindi, Hinglish, Gujarati, Marathi, Tamil, Bengali). "
                "Keep responses under 3 paragraphs or use clean bullet points."
            )
            messages = [{"role": "system", "content": system_prompt}]
            if body.history:
                for h in body.history[-6:]:
                    if h.get("role") in {"user", "assistant"} and h.get("content"):
                        messages.append({"role": h["role"], "content": str(h["content"])[:1000]})
            messages.append({"role": "user", "content": message[:1000]})
            
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.3,
                max_tokens=600,
            )
            reply = response.choices[0].message.content
            return {"success": True, "reply": reply, "engine": "Groq Llama 3.1"}
        except Exception as e:
            print(f"[Groq Chatbot Error] {e}")
            
    # Intelligent Heuristic Fallback
    lower = message.lower()
    if any(k in lower for k in ["hello", "hi", "namaste", "pranam", "hey", "namaskar"]):
        reply = "Namaste! 🙏 I am Jan Sevak, your AI Civic Innovation Assistant for NagrikSnap. How can I help you today with reporting challenges, university solutions, CSR funding, or tracking?"
    elif any(k in lower for k in ["report", "complaint", "submit", "darj", "photo"]):
        reply = "📸 **To report a societal challenge:**\n\n1. Go to **Report Challenge**\n2. Snap/upload evidence photo or video\n3. Describe the problem in your words\n4. Pin your location on the map & enter your mobile number\n\nOur AI will categorize it and notify university innovators!"
    elif any(k in lower for k in ["track", "status", "pragati"]):
        reply = "🔍 **To track challenge progress:**\n\nVisit **Track Status**, enter your Tracking ID (e.g. `CH-2026-XXXX`) or mobile number to see live updates from Crowdsourced ➔ AI Scoped ➔ Univ In-Progress ➔ CSR Funded ➔ Pilot Solved!"
    elif any(k in lower for k in ["university", "college", "student", "proposal", "research"]):
        reply = "🎓 **For University Innovators:**\n\nBrowse open challenges in the University Portal, form student research teams, and submit technical proposals. Approved projects receive industry CSR funding and academic innovation credits!"
    elif any(k in lower for k in ["csr", "industry", "sponsor", "fund", "grant", "company"]):
        reply = "🏢 **For Industry & CSR Partners:**\n\nVisit the CSR Portal to discover verified challenges aligned with UN Sustainable Development Goals (SDGs) and pledge tax-exempt CSR grants to student engineering teams."
    elif any(k in lower for k in ["govt", "government", "admin", "authority", "pilot", "permit"]):
        reply = "🏛️ **For Government Authorities:**\n\nThe Government Portal allows municipal nodal officers to review challenges, approve pilot field permits, track milestone proof, and certify resolution on the ground."
    else:
        reply = f"Thank you for contacting NagrikSnap! Regarding '{message}': our platform connects citizens with universities for research and industry for CSR funding. You can report an issue, submit a solution, or track live progress."
        
    return {"success": True, "reply": reply, "engine": "Heuristic Engine"}


# ===== Static Uploads Serving =====
@app.get("/uploads/{filename}")
def serve_upload(filename: str, user=Depends(require_case_member)):
    # Complaint evidence is private by default. Only an authenticated case-room
    # participant for the associated challenge (or an administrator) may retrieve it.
    if not re.fullmatch(r"CH-2026-[A-F0-9]+_[a-f0-9]+\.(jpg|png|webp)", filename):
        raise HTTPException(status_code=404, detail="File not found")
    challenge_id = filename.split("_", 1)[0]
    if not can_access_case_room(challenge_id, user):
        raise HTTPException(status_code=404, detail="File not found")
    # In S3 mode, redirect authenticated requests to a secure 5-minute pre-signed S3 URL
    if getattr(evidence_storage, "STORAGE_MODE", "local") == "s3":
        presigned_url = evidence_storage.generate_presigned_download_url(filename, expires_in=300)
        if presigned_url:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=presigned_url, status_code=307)
    try:
        stored = evidence_storage.read_evidence(filename)
    except Exception:
        raise HTTPException(status_code=503, detail="Evidence storage is temporarily unavailable")
    if stored is None:
        raise HTTPException(status_code=404, detail="File not found")
    content, media = stored
    return Response(content=content, media_type=media, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": "inline"})


# ===== Mount Frontend Web Application =====
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
