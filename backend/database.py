"""
CivicInnovate / SamadhanSetu Database - SQLite Persistence Layer
Built for SIH 2026 Problem Statement 26043:
"A digital platform to crowdsource societal challenges and facilitate collaborative problem solving through universities and industry partnerships"
"""

import sqlite3
import os
import json
import threading
import re
from datetime import datetime

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
    else:
        load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

try:
    import psycopg
    from psycopg.rows import dict_row
    PSYCOPG_AVAILABLE = True
except ImportError:
    PSYCOPG_AVAILABLE = False
    if IS_POSTGRES:
        raise RuntimeError("DATABASE_URL is set but psycopg is not installed. Run: pip install psycopg[binary]")

DB_PATH = os.getenv("NAGRIKSNAP_SQLITE_PATH", os.path.join(os.path.dirname(__file__), "nagriksnap.db"))
_lock = threading.Lock()


class RowWrapper(dict):
    """Dictionary that also supports integer indexing like sqlite3.Row."""
    def __init__(self, d, tuple_vals=None):
        super().__init__(d)
        self._tuple_vals = tuple_vals or tuple(d.values())
    def __getitem__(self, item):
        if isinstance(item, int):
            return self._tuple_vals[item]
        return super().__getitem__(item)


class PostgresCursorWrapper:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, query, params=None):
        q = query.strip().upper()
        # Ignore PRAGMA and SQLite explicit transaction starts (psycopg manages transactions)
        if q.startswith("PRAGMA") or q.startswith("BEGIN"):
            return self
        converted_query = re.sub(r'\?', '%s', query)
        if params is not None:
            self._cur.execute(converted_query, params)
        else:
            self._cur.execute(converted_query)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return RowWrapper(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [RowWrapper(r) for r in rows]

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()


class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor(row_factory=dict_row))

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _connect():
    if IS_POSTGRES:
        raw_conn = psycopg.connect(DATABASE_URL)
        return PostgresConnectionWrapper(raw_conn)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _migrate_columns(conn):
    """Safely check and add missing columns to existing SQLite tables."""
    if IS_POSTGRES:
        return
    # Check complaints columns
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(complaints)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    needed_cols = [
        ("title", "TEXT DEFAULT ''"),
        ("category", "TEXT DEFAULT 'Infrastructure'"),
        ("sdg_tag", "TEXT DEFAULT 'SDG 11: Sustainable Cities'"),
        ("bounty_amount", "REAL DEFAULT 0.0"),
        ("assigned_team_id", "TEXT"),
        ("assigned_team_name", "TEXT"),
        ("assigned_university", "TEXT"),
        ("sponsor_id", "TEXT"),
        ("sponsor_name", "TEXT"),
        ("sponsor_grant", "REAL DEFAULT 0.0"),
        ("ai_tech_stack", "TEXT DEFAULT ''"),
        ("ai_recommended_depts", "TEXT DEFAULT ''"),
        ("ai_summary", "TEXT DEFAULT ''"),
        ("district", "TEXT DEFAULT ''"),
        ("owner_user_id", "TEXT"),
    ]
    for col_name, col_type in needed_cols:
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE complaints ADD COLUMN {col_name} {col_type};")
            except Exception as e:
                print(f"[DB Migration] Notice on {col_name}: {e}")

    # Check users columns
    cursor.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    needed_user_cols = [
        ("organization", "TEXT DEFAULT ''"),
        ("email", "TEXT DEFAULT ''"),
    ]
    for col_name, col_type in needed_user_cols:
        if col_name not in user_cols:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")
            except Exception as e:
                print(f"[DB Migration] Notice on user {col_name}: {e}")

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(lower(email)) WHERE email IS NOT NULL AND trim(email) != ''")
    conn.execute("""CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        used_at TEXT DEFAULT '', created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_tokens(user_id, created_at)")

    # Ownership for cross-role submissions (safe for existing SQLite databases).
    for table in ("proposals", "sponsorships"):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        if "submitted_by_user_id" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN submitted_by_user_id TEXT DEFAULT ''")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_submitter ON {table}(submitted_by_user_id, created_at)")

    # Government milestone review fields (safe migration for existing databases).
    cursor.execute("PRAGMA table_info(milestones)")
    milestone_cols = {row[1] for row in cursor.fetchall()}
    for col_name, col_type in [
        ("review_decision", "TEXT DEFAULT 'pending_review'"),
        ("review_note", "TEXT DEFAULT ''"),
        ("reviewer_user_id", "TEXT DEFAULT ''"),
        ("reviewer_name", "TEXT DEFAULT ''"),
        ("reviewer_role", "TEXT DEFAULT ''"),
        ("reviewed_at", "TEXT DEFAULT ''"),
    ]:
        if col_name not in milestone_cols:
            conn.execute(f"ALTER TABLE milestones ADD COLUMN {col_name} {col_type}")

    # Check reviews columns
    cursor.execute("PRAGMA table_info(reviews)")
    rev_cols = {row[1] for row in cursor.fetchall()}
    if "impact_score" not in rev_cols:
        try:
            conn.execute("ALTER TABLE reviews ADD COLUMN impact_score INTEGER DEFAULT 5;")
        except Exception:
            pass


def init_db():
    """Create tables if they don't exist and seed initial demo data."""
    if IS_POSTGRES:
        # Schema and records in PostgreSQL are already provisioned and persistent
        return
    with _lock:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS complaint_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT NOT NULL,
                    actor_user_id TEXT DEFAULT '',
                    actor_name TEXT DEFAULT '',
                    actor_role TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    changed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_status_history_complaint ON complaint_status_history(complaint_id, id);
                CREATE TABLE IF NOT EXISTS notification_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    channel TEXT NOT NULL DEFAULT 'sms',
                    recipient TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','sent','failed')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    next_attempt_at TEXT NOT NULL,
                    sent_at TEXT DEFAULT '',
                    delivery_mode TEXT NOT NULL DEFAULT 'unknown',
                    last_error TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_outbox_due ON notification_outbox(status, next_attempt_at, id);
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id TEXT NOT NULL DEFAULT '',
                    actor_name TEXT NOT NULL DEFAULT '',
                    actor_role TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL DEFAULT '',
                    ip_address TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    user_id TEXT DEFAULT '',
                    expires_at REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bucket_hash TEXT NOT NULL,
                    occurred_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rate_limit_bucket_time ON rate_limit_events(bucket_hash, occurred_at);
                CREATE TABLE IF NOT EXISTS organization_verification_requests (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    requested_role TEXT NOT NULL CHECK(requested_role IN ('university','industry')),
                    organization_name TEXT NOT NULL,
                    department TEXT DEFAULT '',
                    contact_email TEXT NOT NULL,
                    website TEXT DEFAULT '',
                    justification TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
                    reviewer_id TEXT DEFAULT '',
                    reviewer_note TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT DEFAULT '',
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_org_verification_status ON organization_verification_requests(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_org_verification_user ON organization_verification_requests(user_id, created_at);

                CREATE TABLE IF NOT EXISTS users (
                    id            TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    username      TEXT,
                    phone         TEXT NOT NULL,
                    password_hash TEXT,
                    role          TEXT NOT NULL DEFAULT 'citizen',
                    organization  TEXT DEFAULT '',
                    department    TEXT DEFAULT '',
                    address       TEXT DEFAULT '',
                    lat           REAL,
                    lng           REAL,
                    created_at    TEXT,
                    updated_at    TEXT,
                    last_login    TEXT
                );

                CREATE TABLE IF NOT EXISTS complaints (
                    id                  TEXT PRIMARY KEY,
                    title               TEXT DEFAULT '',
                    description         TEXT NOT NULL,
                    phone               TEXT NOT NULL,
                    address             TEXT,
                    lat                 REAL,
                    lng                 REAL,
                    department          TEXT DEFAULT 'General Civic',
                    category            TEXT DEFAULT 'Infrastructure',
                    sdg_tag             TEXT DEFAULT 'SDG 11: Sustainable Cities',
                    priority            TEXT DEFAULT 'Medium',
                    status              TEXT DEFAULT 'Crowdsourced',
                    photo               TEXT,
                    bounty_amount       REAL DEFAULT 0.0,
                    assigned_admin      TEXT,
                    assigned_admin_id   TEXT,
                    assigned_admin_name TEXT,
                    assigned_team_id    TEXT,
                    assigned_team_name  TEXT,
                    assigned_university TEXT,
                    sponsor_id          TEXT,
                    sponsor_name        TEXT,
                    sponsor_grant       REAL DEFAULT 0.0,
                    ai_tech_stack       TEXT DEFAULT '',
                    ai_recommended_depts TEXT DEFAULT '',
                    ai_summary          TEXT DEFAULT '',
                    created_at          TEXT
                );

                CREATE TABLE IF NOT EXISTS proposals (
                    id              TEXT PRIMARY KEY,
                    challenge_id    TEXT NOT NULL,
                    team_name       TEXT NOT NULL,
                    university_name TEXT NOT NULL,
                    lead_name       TEXT NOT NULL,
                    lead_email      TEXT NOT NULL,
                    lead_phone      TEXT DEFAULT '',
                    faculty_mentor  TEXT DEFAULT '',
                    tech_stack      TEXT DEFAULT '',
                    abstract        TEXT NOT NULL,
                    github_url      TEXT DEFAULT '',
                    demo_url        TEXT DEFAULT '',
                    budget_needed   REAL DEFAULT 0.0,
                    status          TEXT DEFAULT 'submitted',
                    created_at      TEXT
                );

                CREATE TABLE IF NOT EXISTS sponsorships (
                    id              TEXT PRIMARY KEY,
                    challenge_id    TEXT NOT NULL,
                    company_name    TEXT NOT NULL,
                    contact_name    TEXT NOT NULL,
                    contact_email   TEXT NOT NULL,
                    csr_domain      TEXT DEFAULT '',
                    pledge_amount   REAL DEFAULT 0.0,
                    resources_offered TEXT DEFAULT '',
                    mentor_name     TEXT DEFAULT '',
                    status          TEXT DEFAULT 'active',
                    created_at      TEXT
                );

                CREATE TABLE IF NOT EXISTS case_room_messages (
                    id              TEXT PRIMARY KEY,
                    challenge_id    TEXT NOT NULL,
                    sender_name     TEXT NOT NULL,
                    sender_role     TEXT NOT NULL,
                    sender_org      TEXT DEFAULT '',
                    message         TEXT NOT NULL,
                    attachment_url  TEXT DEFAULT '',
                    created_at      TEXT
                );

                CREATE TABLE IF NOT EXISTS milestones (
                    id               TEXT PRIMARY KEY,
                    challenge_id     TEXT NOT NULL,
                    title            TEXT NOT NULL,
                    description      TEXT DEFAULT '',
                    progress_percent INTEGER DEFAULT 0,
                    status           TEXT DEFAULT 'pending',
                    proof_url        TEXT DEFAULT '',
                    created_at       TEXT
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    id            TEXT PRIMARY KEY,
                    complaint_id  TEXT NOT NULL,
                    rating        INTEGER NOT NULL,
                    comment       TEXT DEFAULT '',
                    name          TEXT DEFAULT 'Citizen',
                    phone         TEXT DEFAULT '',
                    department    TEXT DEFAULT '',
                    impact_score  INTEGER DEFAULT 5,
                    created_at    TEXT
                );
                CREATE TABLE IF NOT EXISTS university_profiles (
                    user_id TEXT PRIMARY KEY,
                    organization_name TEXT NOT NULL,
                    expertise TEXT NOT NULL DEFAULT '',
                    sdg_focus TEXT NOT NULL DEFAULT '',
                    past_projects INTEGER NOT NULL DEFAULT 0 CHECK(past_projects >= 0),
                    available_slots INTEGER NOT NULL DEFAULT 0 CHECK(available_slots >= 0),
                    districts TEXT NOT NULL DEFAULT '',
                    website TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_university_profiles_org ON university_profiles(organization_name);
                CREATE TABLE IF NOT EXISTS collaboration_members (
                    id TEXT PRIMARY KEY,
                    challenge_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    member_role TEXT NOT NULL DEFAULT 'member',
                    status TEXT NOT NULL DEFAULT 'invited' CHECK(status IN ('invited','accepted','declined','removed')),
                    invited_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(challenge_id, user_id),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_collab_members_challenge ON collaboration_members(challenge_id, status);
                CREATE INDEX IF NOT EXISTS idx_collab_members_user ON collaboration_members(user_id, status);
                CREATE TABLE IF NOT EXISTS collaboration_tasks (
                    id TEXT PRIMARY KEY,
                    challenge_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    assigned_to TEXT,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo','in_progress','blocked','done')),
                    priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
                    due_date TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(assigned_to) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_collab_tasks_challenge ON collaboration_tasks(challenge_id, status);
                """
            )
            conn.commit()

            # Safely migrate any missing columns
            _migrate_columns(conn)

            # Create Indexes
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_complaints_phone   ON complaints(phone);
                CREATE INDEX IF NOT EXISTS idx_complaints_status  ON complaints(status);
                CREATE INDEX IF NOT EXISTS idx_complaints_dept    ON complaints(department);
                CREATE INDEX IF NOT EXISTS idx_complaints_sdg     ON complaints(sdg_tag);
                CREATE INDEX IF NOT EXISTS idx_proposals_chal     ON proposals(challenge_id);
                CREATE INDEX IF NOT EXISTS idx_sponsors_chal      ON sponsorships(challenge_id);
                CREATE INDEX IF NOT EXISTS idx_caseroom_chal      ON case_room_messages(challenge_id);
                CREATE INDEX IF NOT EXISTS idx_milestones_chal    ON milestones(challenge_id);
                CREATE INDEX IF NOT EXISTS idx_users_phone        ON users(phone);
                CREATE INDEX IF NOT EXISTS idx_reviews_complaint  ON reviews(complaint_id);
                """
            )
            # Backfill a baseline event for existing complaints with no history.
            conn.execute("""INSERT INTO complaint_status_history
                (complaint_id, old_status, new_status, actor_user_id, actor_name, actor_role, note, changed_at)
                SELECT c.id, NULL, COALESCE(NULLIF(c.status,''),'Crowdsourced'), '', 'System', 'system',
                       'Initial status recorded during status-history rollout', COALESCE(c.created_at, datetime('now'))
                FROM complaints c WHERE NOT EXISTS
                (SELECT 1 FROM complaint_status_history h WHERE h.complaint_id=c.id)""")
            conn.commit()
        finally:
            conn.close()

    _seed_sih_demo_data()


def _seed_sih_demo_data():
    """Seed sample SIH 26043 challenges, university proposals, CSR sponsors, and case rooms."""
    with _lock:
        conn = _connect()
        try:
            cnt = conn.execute("SELECT COUNT(*) c FROM complaints").fetchone()["c"]
            if cnt <= 2:
                demo_challenges = [
                    (
                        "CH-2026-001",
                        "Smart IoT Water Distribution Leakage & Pressure Sensor Grid",
                        "Over 35% of potable water is lost to underground pipe bursts and illegal tapping across Ward 7. The community faces severe drinking water shortages every summer.",
                        "9876543210",
                        "Sector 12 Municipal Water Line, New Delhi",
                        28.5921, 77.0460,
                        "Water Resources",
                        "Water & Sanitation",
                        "SDG 6: Clean Water & Sanitation",
                        "High",
                        "Under Development",
                        "",
                        75000.0,
                        "TEAM-AQUASENSE",
                        "AquaSense IIT Delhi",
                        "IIT Delhi - Dept of Civil & IoT Engg",
                        "SPON-01",
                        "Tata Sustainability Fund",
                        150000.0,
                        "Acoustic hydrophones, ESP32, LoRaWAN, TensorFlow Lite edge anomaly detection",
                        "Civil Engineering, IoT & Embedded Systems, AI/ML",
                        "Deploying an acoustic vibration & flow sensor network to pinpoint underground pipe leakage with <1m accuracy.",
                        datetime.now().isoformat()
                    ),
                    (
                        "CH-2026-002",
                        "Solar-Powered Decentralized Organic Waste Composting & Biogas Unit",
                        "Commercial vegetable market generates 4 tons of organic wet waste daily, causing open dumping, methane emissions, and foul smell near residential quarters.",
                        "9876543211",
                        "APMC Subzi Mandi, Sector 18, Noida",
                        28.5700, 77.3200,
                        "Waste Management",
                        "Waste Management & Circular Economy",
                        "SDG 12: Responsible Consumption & Production",
                        "High",
                        "Open For Bidding",
                        "",
                        100000.0,
                        None, None, None,
                        "SPON-02",
                        "Infosys Green Innovation CSR",
                        200000.0,
                        "Automated shredder, anaerobic digester, solar thermal heater, IoT methane monitor",
                        "Biotechnology, Mechanical Engineering, Environmental Science",
                        "Continuous thermophilic bio-digester converting 1 ton wet waste daily into bio-CNG and nutrient fertilizer.",
                        datetime.now().isoformat()
                    ),
                    (
                        "CH-2026-003",
                        "AI Automated Road Quality & Pothole Hazard Mapper for Public Buses",
                        "Dangerous potholes on transit corridors cause accidents and delayed ambulances. Municipal manual road inspection takes months.",
                        "9876543212",
                        "Ring Road Corridor, South Delhi",
                        28.5494, 77.2001,
                        "Roads & Infrastructure",
                        "Smart Mobility & Transport",
                        "SDG 11: Sustainable Cities & Communities",
                        "Medium",
                        "Pilot Deployed",
                        "",
                        50000.0,
                        "TEAM-VISIONROAD",
                        "VisionRoads DTU",
                        "Delhi Technological University",
                        "SPON-03",
                        "L&T Smart City Technologies",
                        100000.0,
                        "YOLOv8 computer vision, Raspberry Pi 5, GPS tracker, Web Dashboard",
                        "Computer Science, Transportation Engineering",
                        "Dashcam AI system mounted on 15 municipal buses detecting road defects in real-time.",
                        datetime.now().isoformat()
                    ),
                    (
                        "CH-2026-004",
                        "Low-Cost Decentralized Solar Cold Storage for Smallholder Farmers",
                        "Perishable tomato and green chilli crops rot within 48 hours post-harvest due to lack of affordable grid cold storage.",
                        "9876543213",
                        "Rural Mandi Cluster, Alwar Outskirts",
                        27.5530, 76.6346,
                        "Agriculture & Rural Development",
                        "Rural & Agricultural Tech",
                        "SDG 2: Zero Hunger & SDG 7: Clean Energy",
                        "Medium",
                        "Open For Bidding",
                        "",
                        120000.0,
                        None, None, None,
                        None, None, 0.0,
                        "Phase change materials (PCM), DC inverter compressor, 3kW solar array",
                        "Agricultural Engineering, Renewable Energy, Thermal Engg",
                        "Passive PCM thermal battery cold room maintaining 4°C-8°C without diesel backup.",
                        datetime.now().isoformat()
                    )
                ]

                for ch in demo_challenges:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO complaints 
                        (id, title, description, phone, address, lat, lng, department, category, sdg_tag, priority, status, photo, bounty_amount, assigned_team_id, assigned_team_name, assigned_university, sponsor_id, sponsor_name, sponsor_grant, ai_tech_stack, ai_recommended_depts, ai_summary, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        ch
                    )

                # Seed proposals
                conn.execute(
                    """
                    INSERT OR REPLACE INTO proposals
                    (id, challenge_id, team_name, university_name, lead_name, lead_email, lead_phone, faculty_mentor, tech_stack, abstract, github_url, demo_url, budget_needed, status, created_at)
                    VALUES
                    ('PROP-01', 'CH-2026-001', 'AquaSense IITD', 'IIT Delhi', 'Rohan Sharma', 'rohan.s@iitd.ac.in', '9811122233', 'Prof. V. Ramanathan', 'C++, LoRaWAN, PyTorch, ESP32', 'Deploying non-invasive acoustic vibration probes connected via 868MHz LoRa mesh to municipal telemetry server.', 'https://github.com/aquasense-iitd/water-leak-ai', 'https://aquasense.demo.iitd.ac.in', 85000, 'accepted', ?),
                    ('PROP-02', 'CH-2026-001', 'HydroTech NITK', 'NIT Surathkal', 'Ananya Hegde', 'ananya@nitk.edu.in', '9822233344', 'Dr. S. K. Rao', 'Ultrasonic sensors, Arduino, Flutter App', 'Ultrasonic differential flow measuring nodes with GSM fallback.', 'https://github.com/nitk-hydro/smart-flow', '', 95000, 'shortlisted', ?),
                    ('PROP-03', 'CH-2026-003', 'VisionRoads DTU', 'Delhi Technological University', 'Piyush Verma', 'piyush.v@dtu.ac.in', '9833344455', 'Prof. Neha Gupta', 'Python, YOLOv8, OpenCV, FastAPI, Leaflet', 'Edge-AI dashcam device processing 1080p road video at 30fps with automatic geocoded pothole severity heatmapping.', 'https://github.com/dtu-civic/vision-roads', 'https://visionroads.dtu.ac.in', 45000, 'accepted', ?)
                    """,
                    (datetime.now().isoformat(), datetime.now().isoformat(), datetime.now().isoformat())
                )

                # Seed sponsorships
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sponsorships
                    (id, challenge_id, company_name, contact_name, contact_email, csr_domain, pledge_amount, resources_offered, mentor_name, status, created_at)
                    VALUES
                    ('SPON-01', 'CH-2026-001', 'Tata Sustainability Fund', 'Vikramaditya Sen', 'csr@tatasustainability.com', 'Water Conservation & Urban Tech', 150000, '10 LoRa Gateway Base Stations + Azure IoT credits', 'Dr. Arvind Joshi (Chief Water Architect)', 'active', ?),
                    ('SPON-02', 'CH-2026-002', 'Infosys Green Innovation CSR', 'Pooja Kulkarni', 'csr-green@infosys.com', 'Circular Economy & Bioenergy', 200000, 'Fabrication lab access, biological culture starter kits', 'Er. Rajesh Nair', 'active', ?),
                    ('SPON-03', 'CH-2026-003', 'L&T Smart City Technologies', 'Siddharth Roy', 'smartcities@larsentoubro.com', 'Smart Transport & Vision AI', 100000, '5 Edge Compute Kits + Integration with City Command Center', 'Manish Kapoor (VP Smart Mobility)', 'active', ?)
                    """,
                    (datetime.now().isoformat(), datetime.now().isoformat(), datetime.now().isoformat())
                )

                # Seed case room messages
                conn.execute(
                    """
                    INSERT OR REPLACE INTO case_room_messages
                    (id, challenge_id, sender_name, sender_role, sender_org, message, attachment_url, created_at)
                    VALUES
                    ('MSG-01', 'CH-2026-001', 'Er. R. K. Saxena', 'govt', 'Delhi Jal Board (DJB)', 'Welcome team IIT Delhi & Tata Sustainability. We have mapped the 4km feeder pipeline on Ward 7 and granted site test permits.', '', ?),
                    ('MSG-02', 'CH-2026-001', 'Rohan Sharma (Lead)', 'university', 'AquaSense IIT Delhi', 'Thank you Sir! We have calibrated our 6 LoRa hydrophone nodes. Sensor data is streaming to the test dashboard.', 'https://github.com/aquasense-iitd/water-leak-ai', ?),
                    ('MSG-03', 'CH-2026-001', 'Dr. Arvind Joshi', 'industry', 'Tata Sustainability Fund', 'Great milestone. We have dispatched the 2 high-gain gateway antennas and unlocked Rs. 75,000 for field fabrication.', '', ?)
                    """,
                    (datetime.now().isoformat(), datetime.now().isoformat(), datetime.now().isoformat())
                )

                # Seed milestones
                conn.execute(
                    """
                    INSERT OR REPLACE INTO milestones
                    (id, challenge_id, title, description, progress_percent, status, proof_url, created_at)
                    VALUES
                    ('MS-01', 'CH-2026-001', 'Lab Prototype & Bench Testing', 'Acoustic sensor circuit tested on pressurized pipe test rig in fluid mechanics lab.', 100, 'verified', 'https://aquasense.demo.iitd.ac.in/lab-report.pdf', ?),
                    ('MS-02', 'CH-2026-001', 'Field Node Deployment (6 Units)', 'Installed at 6 junction chambers along Sector 12 trunk line.', 100, 'verified', 'https://aquasense.demo.iitd.ac.in/field-photos.zip', ?),
                    ('MS-03', 'CH-2026-001', 'Real-Time Leakage Alert Validation', 'Live pilot detecting artificial leak with 0.8m precision and sending SMS alert to DJB.', 75, 'pending', '', ?)
                    """,
                    (datetime.now().isoformat(), datetime.now().isoformat(), datetime.now().isoformat())
                )

                conn.commit()
        finally:
            conn.close()


def _seed_demo_users():
    """Ensure standard demo users for all roles exist with Password123!"""
    try:
        from argon2 import PasswordHasher
        pwd_hash = PasswordHasher().hash("Password123!")
    except Exception:
        pwd_hash = "salt123:" + hashlib.sha256(("salt123" + "Password123!").encode()).hexdigest()
    
    now = datetime.now().isoformat()
    demo_accounts = [
        # Government
        ("U-GOVT-001", "Rakesh Sharma (Nodal Officer)", "government", "9876540001", "demo.government@example.test", pwd_hash, "govt_admin", "Municipal Corporation", "Public Works / Roads"),
        ("U-GOVT-002", "Rakesh Sharma", "govt", "9876540002", "demo.govt@example.test", pwd_hash, "govt_admin", "Municipal Corporation", "Public Works / Roads"),
        # Industry
        ("U-IND-001", "Amit Verma (CSR Director)", "industry", "9876540003", "demo.industry@example.test", pwd_hash, "industry", "TechNova Solutions Ltd.", "CSR Foundation"),
        # University
        ("U-UNIV-001", "Prof. Rajesh Iyer (Research Dean)", "university", "9876540004", "demo.university@example.test", pwd_hash, "university", "Apex Engineering Institute", "Computer Science & Engineering"),
        # Admin
        ("U-ADM-001", "Central Platform Administrator", "admin", "9876540005", "demo.admin@example.test", pwd_hash, "admin", "Smart City Innovation Mission", "System Operations"),
        # Citizen
        ("U-CIT-001", "Demo Citizen", "citizen", "9876540006", "demo.citizen@example.test", pwd_hash, "citizen", "", ""),
        ("U-CIT-002", "Aman Singh", "aman_singh89", "9876540007", "aman.2710.singh.1947@gmail.com", pwd_hash, "citizen", "", ""),
    ]
    with _lock:
        conn = _connect()
        try:
            for acc in demo_accounts:
                uid, name, uname, phone, email, phash, role, org, dept = acc
                row = conn.execute("SELECT id FROM users WHERE lower(email)=lower(?) OR lower(username)=lower(?) LIMIT 1", (email, uname)).fetchone()
                if row:
                    conn.execute(
                        "UPDATE users SET name=?, username=?, email=?, password_hash=?, role=?, organization=?, department=?, updated_at=? WHERE id=?",
                        (name, uname, email, phash, role, org, dept, now, row["id"])
                    )
                else:
                    conn.execute(
                        """INSERT INTO users (id, name, username, phone, email, password_hash, role, organization, department, address, lat, lng, created_at, updated_at, last_login)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'National Capital Region', 28.6139, 77.2090, ?, ?, ?)""",
                        (uid, name, uname, phone, email, phash, role, org, dept, now, now, now)
                    )
            conn.commit()
        except Exception as e:
            print(f"[Seed Users Notice] {e}")
        finally:
            conn.close()


# ===================== USERS & AUTH =====================
def get_users():
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_user_by_email(email):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE lower(email)=lower(?) LIMIT 1", ((email or "").strip(),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def create_password_reset_token(token_id, user_id, token_hash, expires_at):
    with _lock:
        conn = _connect()
        try:
            conn.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at=''", (datetime.now().isoformat(), user_id))
            conn.execute("INSERT INTO password_reset_tokens (id,user_id,token_hash,expires_at,attempts,used_at,created_at) VALUES (?,?,?,?,0,'',?)", (token_id,user_id,token_hash,expires_at,datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()


def get_password_reset_token(token_id):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM password_reset_tokens WHERE id=?", (token_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def increment_reset_attempt(token_id):
    with _lock:
        conn = _connect()
        try:
            conn.execute("UPDATE password_reset_tokens SET attempts=attempts+1 WHERE id=?", (token_id,))
            conn.commit()
        finally:
            conn.close()


def consume_password_reset_token(token_id, password_hash):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT user_id,used_at,expires_at FROM password_reset_tokens WHERE id=?", (token_id,)).fetchone()
            if not row or row["used_at"] or row["expires_at"] <= datetime.now().isoformat():
                conn.rollback(); return False
            conn.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?", (password_hash, datetime.now().isoformat(), row["user_id"]))
            conn.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=?", (datetime.now().isoformat(), token_id))
            conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (row["user_id"],))
            conn.commit(); return True
        finally:
            conn.close()

def get_user_by_phone(phone, role=None):
    with _lock:
        conn = _connect()
        try:
            if role:
                row = conn.execute("SELECT * FROM users WHERE phone=? AND role=?", (phone, role)).fetchone()
            else:
                row = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def search_collaboration_users(query: str, exclude_user_id: str = "", limit: int = 20):
    """Return a minimal, privacy-conscious directory for authorised project invitations."""
    term = (query or "").strip()
    if len(term) < 2:
        return []
    pattern = f"%{term}%"
    allowed_roles = ("student", "faculty", "university", "industry", "mentor", "citizen")
    placeholders = ",".join("?" for _ in allowed_roles)
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                f"SELECT id, name, username, role, organization, department FROM users "
                f"WHERE id != ? AND role IN ({placeholders}) AND "
                "(name LIKE ? OR username LIKE ? OR organization LIKE ? OR department LIKE ?) "
                "ORDER BY name COLLATE NOCASE LIMIT ?",
                (exclude_user_id, *allowed_roles, pattern, pattern, pattern, pattern, max(1, min(int(limit), 20))),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def get_user_by_id(user_id):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def update_user_password(user_id: str, password_hash: str):
    with _lock:
        conn = _connect()
        try:
            conn.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?", (password_hash, datetime.now().isoformat(), user_id))
            conn.commit()
        finally:
            conn.close()


def update_user_profile(user_id: str, name: str, email: str, phone: str, address: str = ""):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE users SET name=?, email=?, phone=?, address=?, updated_at=? WHERE id=?",
                (name, email, phone, address, datetime.now().isoformat(), user_id)
            )
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def add_user(user: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO users 
                (id, name, username, phone, email, password_hash, role, organization, department, address, lat, lng, created_at, updated_at, last_login)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    user.get("id"),
                    user.get("name"),
                    user.get("username"),
                    str(user.get("phone", "")),
                    (user.get("email") or "").strip().lower(),
                    user.get("password_hash"),
                    user.get("role", "citizen"),
                    user.get("organization", ""),
                    user.get("department", ""),
                    user.get("address", ""),
                    user.get("lat"),
                    user.get("lng"),
                    user.get("created_at") or datetime.now().isoformat(),
                    user.get("updated_at"),
                    user.get("last_login"),
                ),
            )
            conn.commit()
        finally:
            conn.close()


# ================= SHARED RATE LIMITING =================
def consume_rate_limit(bucket_hash: str, limit: int, window_seconds: int = 60, now: float = None) -> bool:
    """Atomic SQLite-backed limiter shared by API workers using the same DB file."""
    import time
    now = time.time() if now is None else float(now)
    cutoff = now - max(1, int(window_seconds))
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM rate_limit_events WHERE occurred_at < ?", (cutoff,))
            count = conn.execute("SELECT COUNT(*) FROM rate_limit_events WHERE bucket_hash=? AND occurred_at>=?",
                                 (bucket_hash, cutoff)).fetchone()[0]
            if count >= max(1, int(limit)):
                conn.commit()
                return False
            conn.execute("INSERT INTO rate_limit_events(bucket_hash, occurred_at) VALUES (?,?)", (bucket_hash, now))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ================= ORGANIZATION VERIFICATION =================
def create_org_verification_request(record: dict):
    with _lock:
        conn = _connect()
        try:
            pending = conn.execute(
                "SELECT id FROM organization_verification_requests WHERE user_id=? AND status='pending'",
                (record['user_id'],)
            ).fetchone()
            if pending:
                raise ValueError("A pending verification request already exists")
            conn.execute("""INSERT INTO organization_verification_requests
                (id,user_id,requested_role,organization_name,department,contact_email,website,justification,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                record['id'], record['user_id'], record['requested_role'], record['organization_name'],
                record.get('department',''), record['contact_email'], record.get('website',''),
                record['justification'], 'pending', record['created_at']))
            conn.commit()
            saved = conn.execute("SELECT * FROM organization_verification_requests WHERE id=?", (record['id'],)).fetchone()
            return dict(saved) if saved else None
        finally:
            conn.close()


def get_org_verification_request(request_id: str):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM organization_verification_requests WHERE id=?", (request_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def list_org_verification_requests(status=None, user_id=None, limit=100):
    clauses, params = [], []
    if status:
        clauses.append("status=?"); params.append(status)
    if user_id:
        clauses.append("user_id=?"); params.append(user_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM organization_verification_requests" + where + " ORDER BY created_at DESC LIMIT ?", (*params, max(1,min(int(limit),500)))).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def review_org_verification_request(request_id: str, reviewer_id: str, decision: str, note: str):
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM organization_verification_requests WHERE id=?", (request_id,)).fetchone()
            if not row:
                conn.rollback(); return None
            if row['status'] != 'pending':
                conn.rollback(); raise ValueError("Request has already been reviewed")
            now = datetime.now().isoformat()
            if decision == 'approved':
                conn.execute("UPDATE users SET role=?, organization=?, department=?, updated_at=? WHERE id=?",
                    (row['requested_role'], row['organization_name'], row['department'], now, row['user_id']))
            conn.execute("UPDATE organization_verification_requests SET status=?, reviewer_id=?, reviewer_note=?, reviewed_at=? WHERE id=?",
                (decision, reviewer_id, note, now, request_id))
            conn.commit()
            updated = conn.execute("SELECT * FROM organization_verification_requests WHERE id=?", (request_id,)).fetchone()
            return dict(updated)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ===================== CHALLENGES =====================
def get_complaints(filters=None, search=None, page=1, per_page=50):
    filters = filters or {}
    where = []
    params = []

    if filters.get("status"):
        where.append("LOWER(status)=LOWER(?)")
        params.append(filters["status"])
    if filters.get("priority"):
        where.append("priority=?")
        params.append(filters["priority"])
    if filters.get("department"):
        where.append("LOWER(department) LIKE ?")
        params.append("%" + filters["department"].lower() + "%")
    if filters.get("sdg"):
        where.append("LOWER(sdg_tag) LIKE ?")
        params.append("%" + filters["sdg"].lower() + "%")
    if filters.get("category"):
        where.append("LOWER(category) LIKE ?")
        params.append("%" + filters["category"].lower() + "%")

    if search:
        like = "%" + search.lower() + "%"
        where.append(
            "(LOWER(id) LIKE ? OR phone LIKE ? OR LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(COALESCE(address,'')) LIKE ? OR LOWER(COALESCE(sdg_tag,'')) LIKE ?)"
        )
        params.extend([like, like, like, like, like, like])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with _lock:
        conn = _connect()
        try:
            total = conn.execute(f"SELECT COUNT(*) AS c FROM complaints{where_sql}", params).fetchone()["c"]
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"SELECT * FROM complaints{where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [per_page, offset],
            ).fetchall()
            return [dict(r) for r in rows], total
        finally:
            conn.close()


def get_complaint_by_id(tracking_id):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM complaints WHERE id=?", (tracking_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def add_complaint(c: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO complaints 
                (id, title, description, phone, address, district, lat, lng, department, category, sdg_tag, priority, status, photo, bounty_amount, assigned_admin, assigned_admin_id, assigned_admin_name, assigned_team_id, assigned_team_name, assigned_university, sponsor_id, sponsor_name, sponsor_grant, ai_tech_stack, ai_recommended_depts, ai_summary, created_at, owner_user_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    c.get("id"),
                    c.get("title") or (c.get("description", "")[:60] + "..."),
                    c.get("description", ""),
                    str(c.get("phone", "")),
                    c.get("address"),
                    (c.get("district") or "").strip(),
                    c.get("lat"),
                    c.get("lng"),
                    c.get("department", "General Civic"),
                    c.get("category", "Civic Infrastructure"),
                    c.get("sdg_tag", "SDG 11: Sustainable Cities"),
                    c.get("priority", "Medium"),
                    c.get("status", "Crowdsourced"),
                    c.get("photo"),
                    float(c.get("bounty_amount", 0.0) or 0.0),
                    json.dumps(c.get("assigned_admin")) if c.get("assigned_admin") else None,
                    c.get("assigned_admin_id"),
                    c.get("assigned_admin_name"),
                    c.get("assigned_team_id"),
                    c.get("assigned_team_name"),
                    c.get("assigned_university"),
                    c.get("sponsor_id"),
                    c.get("sponsor_name"),
                    float(c.get("sponsor_grant", 0.0) or 0.0),
                    c.get("ai_tech_stack", ""),
                    c.get("ai_recommended_depts", ""),
                    c.get("ai_summary", ""),
                    c.get("createdAt") or c.get("created_at") or datetime.now().isoformat(),
                    c.get("owner_user_id"),
                ),
            )
            conn.execute("INSERT INTO complaint_status_history (complaint_id, old_status, new_status, actor_user_id, actor_name, actor_role, note, changed_at) VALUES (?,?,?,?,?,?,?,?)",
                         (c.get("id"), None, c.get("status", "Crowdsourced"), "", "System", "system", "Complaint submitted", c.get("createdAt") or c.get("created_at") or datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()


def update_complaint_status_atomic(tracking_id, fields: dict, actor_user_id="", actor_name="", actor_role="", note=""):
    """Update complaint fields and append any status transition in one transaction.

    Returns None when the complaint does not exist; otherwise returns the previous
    and current status. A failed history insert rolls back the complaint update.
    """
    allowed = {
        "title", "description", "department", "category", "sdg_tag", "priority", "status",
        "bounty_amount", "assigned_admin_id", "assigned_admin_name", "assigned_team_id",
        "assigned_team_name", "assigned_university", "sponsor_id", "sponsor_name",
        "sponsor_grant", "ai_tech_stack", "ai_recommended_depts", "ai_summary"
    }
    keys = [key for key in fields if key in allowed and fields[key] is not None]
    if not keys:
        raise ValueError("No valid complaint fields supplied")
    set_clause = ", ".join(f"{key}=?" for key in keys)
    values = [fields[key] for key in keys]
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status, phone FROM complaints WHERE id=?", (tracking_id,)).fetchone()
            if row is None:
                conn.rollback()
                return None
            old_status = row["status"]
            conn.execute(f"UPDATE complaints SET {set_clause} WHERE id=?", values + [tracking_id])
            new_status = fields.get("status", old_status)
            if new_status != old_status:
                changed_at = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO complaint_status_history "
                    "(complaint_id, old_status, new_status, actor_user_id, actor_name, actor_role, note, changed_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (tracking_id, old_status, new_status, actor_user_id or "", actor_name or "",
                     actor_role or "", (note or "")[:500], changed_at),
                )
                # The notification intent is committed atomically with the status/history.
                recipient = (row["phone"] or "").strip()
                if recipient:
                    dedupe_key = f"complaint-status:{tracking_id}:{changed_at}:{new_status}"
                    message = f"NagrikSnap update: complaint {tracking_id} status is now '{new_status}'."
                    conn.execute(
                        "INSERT INTO notification_outbox "
                        "(dedupe_key, channel, recipient, message, status, attempts, created_at, updated_at, next_attempt_at) "
                        "VALUES (?, 'sms', ?, ?, 'pending', 0, ?, ?, ?) "
                        "ON CONFLICT(dedupe_key) DO NOTHING",
                        (dedupe_key, recipient, message[:160], changed_at, changed_at, changed_at),
                    )
            conn.commit()
            return {"old_status": old_status, "status": new_status, "status_changed": new_status != old_status}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def update_complaint(tracking_id, fields: dict):
    allowed = {
        "title", "description", "department", "category", "sdg_tag", "priority", "status",
        "bounty_amount", "assigned_admin_id", "assigned_admin_name", "assigned_team_id",
        "assigned_team_name", "assigned_university", "sponsor_id", "sponsor_name",
        "sponsor_grant", "ai_tech_stack", "ai_recommended_depts", "ai_summary"
    }
    keys = [k for k in fields if k in allowed and fields[k] is not None]
    if not keys:
        return
    set_clause = ", ".join(f"{k}=?" for k in keys)
    values = [fields[k] for k in keys] + [tracking_id]
    with _lock:
        conn = _connect()
        try:
            conn.execute(f"UPDATE complaints SET {set_clause} WHERE id=?", values)
            conn.commit()
        finally:
            conn.close()


# ===================== PROPOSALS =====================
def get_user_proposals(user_id):
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM proposals WHERE submitted_by_user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def get_proposals(challenge_id=None):
    with _lock:
        conn = _connect()
        try:
            if challenge_id:
                rows = conn.execute("SELECT * FROM proposals WHERE challenge_id=? ORDER BY created_at DESC", (challenge_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM proposals ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def add_proposal(p: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO proposals
                (id, challenge_id, team_name, university_name, lead_name, lead_email, lead_phone, faculty_mentor, tech_stack, abstract, github_url, demo_url, budget_needed, status, created_at, submitted_by_user_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    p.get("id"),
                    p.get("challenge_id"),
                    p.get("team_name"),
                    p.get("university_name"),
                    p.get("lead_name"),
                    p.get("lead_email"),
                    str(p.get("lead_phone", "")),
                    p.get("faculty_mentor", ""),
                    p.get("tech_stack", ""),
                    p.get("abstract", ""),
                    p.get("github_url", ""),
                    p.get("demo_url", ""),
                    float(p.get("budget_needed", 0.0) or 0.0),
                    p.get("status", "submitted"),
                    p.get("created_at") or datetime.now().isoformat(),
                    p.get("submitted_by_user_id", ""),
                )
            )
            conn.execute("UPDATE complaints SET status='Open For Bidding' WHERE id=? AND status='Verified'", (p.get("challenge_id"),))
            conn.commit()
        finally:
            conn.close()


def accept_proposal(proposal_id):
    with _lock:
        conn = _connect()
        try:
            prop = conn.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if not prop:
                return None
            prop_dict = dict(prop)
            conn.execute("UPDATE proposals SET status='accepted' WHERE id=?", (proposal_id,))
            conn.execute(
                """
                UPDATE complaints 
                SET status='Under Development', assigned_team_id=?, assigned_team_name=?, assigned_university=?
                WHERE id=?
                """,
                (
                    prop_dict["id"],
                    prop_dict["team_name"],
                    prop_dict["university_name"],
                    prop_dict["challenge_id"]
                )
            )
            conn.commit()
            return prop_dict
        finally:
            conn.close()


# ===================== SPONSORSHIPS =====================
def get_user_sponsorships(user_id):
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM sponsorships WHERE submitted_by_user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def get_sponsorships(challenge_id=None):
    with _lock:
        conn = _connect()
        try:
            if challenge_id:
                rows = conn.execute("SELECT * FROM sponsorships WHERE challenge_id=? ORDER BY created_at DESC", (challenge_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM sponsorships ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def add_sponsorship(s: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO sponsorships
                (id, challenge_id, company_name, contact_name, contact_email, csr_domain, pledge_amount, resources_offered, mentor_name, status, created_at, submitted_by_user_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    s.get("id"),
                    s.get("challenge_id"),
                    s.get("company_name"),
                    s.get("contact_name"),
                    s.get("contact_email"),
                    s.get("csr_domain", ""),
                    float(s.get("pledge_amount", 0.0) or 0.0),
                    s.get("resources_offered", ""),
                    s.get("mentor_name", ""),
                    s.get("status", "active"),
                    s.get("created_at") or datetime.now().isoformat(),
                    s.get("submitted_by_user_id", ""),
                )
            )
            conn.execute(
                """
                UPDATE complaints 
                SET sponsor_id=?, sponsor_name=?, sponsor_grant=sponsor_grant + ?
                WHERE id=?
                """,
                (
                    s.get("id"),
                    s.get("company_name"),
                    float(s.get("pledge_amount", 0.0) or 0.0),
                    s.get("challenge_id")
                )
            )
            conn.commit()
        finally:
            conn.close()


# ===================== CASE ROOM =====================
def get_case_room_messages(challenge_id):
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM case_room_messages WHERE challenge_id=? ORDER BY created_at ASC", (challenge_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def add_case_room_message(m: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO case_room_messages
                (id, challenge_id, sender_name, sender_role, sender_org, message, attachment_url, created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    m.get("id"),
                    m.get("challenge_id"),
                    m.get("sender_name"),
                    m.get("sender_role"),
                    m.get("sender_org", ""),
                    m.get("message"),
                    m.get("attachment_url", ""),
                    m.get("created_at") or datetime.now().isoformat(),
                )
            )
            conn.commit()
        finally:
            conn.close()


# ===================== MILESTONES =====================
def get_milestones(challenge_id):
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM milestones WHERE challenge_id=? ORDER BY created_at ASC", (challenge_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def add_milestone(m: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO milestones
                (id, challenge_id, title, description, progress_percent, status, proof_url, created_at,
                 review_decision, review_note, reviewer_user_id, reviewer_name, reviewer_role, reviewed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    m.get("id"),
                    m.get("challenge_id"),
                    m.get("title"),
                    m.get("description", ""),
                    int(m.get("progress_percent", 0)),
                    m.get("status", "pending"),
                    m.get("proof_url", ""),
                    m.get("created_at") or datetime.now().isoformat(),
                    m.get("review_decision", "pending_review"),
                    m.get("review_note", ""),
                    m.get("reviewer_user_id", ""),
                    m.get("reviewer_name", ""),
                    m.get("reviewer_role", ""),
                    m.get("reviewed_at", ""),
                )
            )
            conn.commit()
        finally:
            conn.close()


def get_milestone_by_id(milestone_id: str):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM milestones WHERE id=?", (milestone_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def review_milestone(milestone_id: str, decision: str, note: str, reviewer: dict):
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE milestones SET review_decision=?, review_note=?, reviewer_user_id=?, reviewer_name=?, reviewer_role=?, reviewed_at=? WHERE id=?",
                (decision, note, reviewer.get("user_id", ""), reviewer.get("name") or reviewer.get("username", "Government reviewer"), reviewer.get("role", ""), datetime.now().isoformat(), milestone_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM milestones WHERE id=?", (milestone_id,)).fetchone()
            conn.commit()
            return dict(row) if row else None
        finally:
            conn.close()


# ===================== P3 COLLABORATION =====================
def list_user_collaboration_members(user_id):
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT m.*,c.title AS challenge_title FROM collaboration_members m LEFT JOIN complaints c ON c.id=m.challenge_id WHERE m.user_id=? ORDER BY m.created_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_collaboration_member(challenge_id, user_id):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM collaboration_members WHERE challenge_id=? AND user_id=?", (challenge_id, user_id)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def list_collaboration_members(challenge_id, include_pending=True):
    with _lock:
        conn = _connect()
        try:
            query = "SELECT m.id,m.challenge_id,m.user_id,m.member_role,m.status,m.invited_by,m.created_at,m.updated_at,u.name,u.role,u.organization FROM collaboration_members m JOIN users u ON u.id=m.user_id WHERE m.challenge_id=?"
            args = [challenge_id]
            if not include_pending:
                query += " AND m.status='accepted'"
            query += " ORDER BY m.created_at ASC"
            return [dict(r) for r in conn.execute(query, args).fetchall()]
        finally:
            conn.close()


def upsert_collaboration_member(record):
    with _lock:
        conn = _connect()
        try:
            conn.execute("""INSERT INTO collaboration_members(id,challenge_id,user_id,member_role,status,invited_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(challenge_id,user_id) DO UPDATE SET
                member_role=excluded.member_role,status=excluded.status,invited_by=excluded.invited_by,updated_at=excluded.updated_at""",
                (record['id'],record['challenge_id'],record['user_id'],record.get('member_role','member'),record.get('status','invited'),record['invited_by'],record['created_at'],record['updated_at']))
            conn.commit()
            row = conn.execute("SELECT * FROM collaboration_members WHERE challenge_id=? AND user_id=?", (record['challenge_id'],record['user_id'])).fetchone()
            return dict(row)
        finally:
            conn.close()


def update_collaboration_member(challenge_id, user_id, status, now):
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("UPDATE collaboration_members SET status=?,updated_at=? WHERE challenge_id=? AND user_id=?", (status,now,challenge_id,user_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def add_collaboration_task(record):
    with _lock:
        conn = _connect()
        try:
            conn.execute("""INSERT INTO collaboration_tasks(id,challenge_id,title,description,assigned_to,created_by,status,priority,due_date,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (record['id'],record['challenge_id'],record['title'],record.get('description',''),record.get('assigned_to'),record['created_by'],record.get('status','todo'),record.get('priority','medium'),record.get('due_date',''),record['created_at'],record['updated_at']))
            conn.commit()
            row=conn.execute("SELECT * FROM collaboration_tasks WHERE id=?",(record['id'],)).fetchone()
            return dict(row)
        finally:
            conn.close()


def list_collaboration_tasks(challenge_id):
    with _lock:
        conn = _connect()
        try:
            rows=conn.execute("SELECT t.*,u.name AS assignee_name FROM collaboration_tasks t LEFT JOIN users u ON u.id=t.assigned_to WHERE t.challenge_id=? ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.due_date, t.created_at",(challenge_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_collaboration_task(task_id):
    with _lock:
        conn = _connect()
        try:
            row=conn.execute("SELECT * FROM collaboration_tasks WHERE id=?",(task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def update_collaboration_task(task_id, fields, now):
    allowed={'title','description','assigned_to','status','priority','due_date'}
    keys=[k for k in fields if k in allowed]
    if not keys:
        return get_collaboration_task(task_id)
    with _lock:
        conn = _connect()
        try:
            clause=", ".join(f"{k}=?" for k in keys)+", updated_at=?"
            conn.execute(f"UPDATE collaboration_tasks SET {clause} WHERE id=?", [fields[k] for k in keys]+[now,task_id])
            conn.commit()
            row=conn.execute("SELECT * FROM collaboration_tasks WHERE id=?",(task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def review_milestone(milestone_id: str, decision: str, note: str, reviewer: dict):
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE milestones SET review_decision=?, review_note=?, reviewer_user_id=?, reviewer_name=?, reviewer_role=?, reviewed_at=? WHERE id=?",
                (decision, note, reviewer.get("user_id", ""), reviewer.get("name") or reviewer.get("username", "Government reviewer"), reviewer.get("role", ""), datetime.now().isoformat(), milestone_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM milestones WHERE id=?", (milestone_id,)).fetchone()
            conn.commit()
            return dict(row) if row else None
        finally:
            conn.close()


def get_milestone_by_id(milestone_id: str):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM milestones WHERE id=?", (milestone_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


# ===================== REVIEWS =====================
def get_reviews():
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_review_by_complaint(complaint_id):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM reviews WHERE complaint_id=?", (complaint_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def add_review(r: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO reviews 
                (id, complaint_id, rating, comment, name, phone, department, impact_score, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    r.get("id"),
                    r.get("complaint_id"),
                    int(r.get("rating", 0)),
                    r.get("comment", ""),
                    r.get("name", "Citizen"),
                    str(r.get("phone", "")),
                    r.get("department", ""),
                    int(r.get("impact_score", 5)),
                    r.get("created_at") or datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


# ===================== ANALYTICS =====================
def analytics():
    with _lock:
        conn = _connect()
        try:
            total_challenges = conn.execute("SELECT COUNT(*) c FROM complaints").fetchone()["c"]
            total_proposals = conn.execute("SELECT COUNT(*) c FROM proposals").fetchone()["c"]
            total_sponsorships = conn.execute("SELECT COUNT(*) c FROM sponsorships").fetchone()["c"]
            total_csr_funds = conn.execute("SELECT COALESCE(SUM(pledge_amount), 0) s FROM sponsorships").fetchone()["s"]

            by_status = {r["status"]: r["c"] for r in conn.execute("SELECT status, COUNT(*) c FROM complaints GROUP BY status")}
            by_priority = {r["priority"]: r["c"] for r in conn.execute("SELECT priority, COUNT(*) c FROM complaints GROUP BY priority")}
            by_department = {r["department"]: r["c"] for r in conn.execute("SELECT department, COUNT(*) c FROM complaints GROUP BY department")}
            by_sdg = {r["sdg_tag"]: r["c"] for r in conn.execute("SELECT sdg_tag, COUNT(*) c FROM complaints GROUP BY sdg_tag")}

            top_universities = [
                dict(r) for r in conn.execute(
                    "SELECT university_name, COUNT(*) as proposals_count FROM proposals GROUP BY university_name ORDER BY proposals_count DESC LIMIT 5"
                ).fetchall()
            ]

            top_sponsors = [
                dict(r) for r in conn.execute(
                    "SELECT company_name, SUM(pledge_amount) as total_grant FROM sponsorships GROUP BY company_name ORDER BY total_grant DESC LIMIT 5"
                ).fetchall()
            ]

            resolved = by_status.get("Resolved", 0) + by_status.get("Pilot Deployed", 0)
            return {
                "total": total_challenges,
                "total_challenges": total_challenges,
                "total_proposals": total_proposals,
                "total_sponsorships": total_sponsorships,
                "total_csr_funds": total_csr_funds,
                "by_status": by_status,
                "by_priority": by_priority,
                "by_department": by_department,
                "by_sdg": by_sdg,
                "top_universities": top_universities,
                "top_sponsors": top_sponsors,
                "resolved_rate": round((resolved / total_challenges) * 100, 2) if total_challenges else 0,
            }
        finally:
            conn.close()


def create_session(token_hash: str, username: str, role: str, user_id: str, expires_at: float):
    with _lock:
        conn = _connect()
        try:
            conn.execute("INSERT INTO auth_sessions(token_hash, username, role, user_id, expires_at, created_at, revoked) VALUES(?,?,?,?,?,?,0)",
                         (token_hash, username, role, user_id or "", expires_at, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()


def get_session(token_hash: str):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT username, role, user_id, expires_at, revoked FROM auth_sessions WHERE token_hash=?", (token_hash,)).fetchone()
            if not row or row["revoked"] or row["expires_at"] < __import__("time").time():
                return None
            return {"username": row["username"], "role": row["role"], "user_id": row["user_id"], "expires": row["expires_at"]}
        finally:
            conn.close()


def revoke_session(token_hash: str):
    with _lock:
        conn = _connect()
        try:
            conn.execute("UPDATE auth_sessions SET revoked=1 WHERE token_hash=?", (token_hash,))
            conn.commit()
        finally:
            conn.close()


def revoke_user_sessions(user_id: str) -> int:
    """Revoke all sessions for an account; returns the number newly revoked."""
    with _lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                "UPDATE auth_sessions SET revoked=1 WHERE user_id=? AND revoked=0",
                (user_id,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
        finally:
            conn.close()


init_db()


# ===================== SECURITY AUDIT LOG =====================
def log_audit(event: dict):
    """Persist security-relevant actions without storing secrets or request bodies."""
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO audit_logs(actor_id, actor_name, actor_role, action, resource_type, resource_id, ip_address, created_at) VALUES(?,?,?,?,?,?,?,?)",
                (event.get("actor_id", ""), event.get("actor_name", ""), event.get("actor_role", ""),
                 event.get("action", ""), event.get("resource_type", ""), event.get("resource_id", ""),
                 event.get("ip_address", ""), event.get("created_at") or datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()


def get_audit_logs(limit=100):
    limit = max(1, min(int(limit), 500))
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ===================== UNIVERSITY MATCHING (P2) =====================
def upsert_university_profile(profile: dict):
    with _lock:
        conn = _connect()
        try:
            conn.execute("""INSERT INTO university_profiles
                (user_id, organization_name, expertise, sdg_focus, past_projects, available_slots, districts, website, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET organization_name=excluded.organization_name,
                expertise=excluded.expertise, sdg_focus=excluded.sdg_focus, past_projects=excluded.past_projects,
                available_slots=excluded.available_slots, districts=excluded.districts, website=excluded.website,
                updated_at=excluded.updated_at""",
                (profile["user_id"], profile["organization_name"], profile.get("expertise", ""),
                 profile.get("sdg_focus", ""), int(profile.get("past_projects", 0)),
                 int(profile.get("available_slots", 0)), profile.get("districts", ""),
                 profile.get("website", ""), profile.get("updated_at") or datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()


def get_university_profile(user_id: str):
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM university_profiles WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def list_university_profiles():
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("""SELECT p.*, u.role AS account_role, u.organization AS approved_organization
                FROM university_profiles p JOIN users u ON u.id=p.user_id
                WHERE u.role='university' ORDER BY p.updated_at DESC""").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ===================== P4 IMPACT ANALYTICS =====================
def impact_analytics(date_from=None, date_to=None, district=None, department=None):
    """Aggregate operational metrics. Complaint metrics support filters; non-complaint totals are explicitly all-time."""
    with _lock:
        conn = _connect()
        try:
            clauses, params = [], []
            if date_from:
                clauses.append("date(created_at) >= date(?)")
                params.append(date_from)
            if date_to:
                clauses.append("date(created_at) <= date(?)")
                params.append(date_to)
            if district:
                clauses.append("lower(trim(COALESCE(district,''))) = lower(trim(?))")
                params.append(district)
            if department:
                clauses.append("lower(trim(COALESCE(department,''))) = lower(trim(?))")
                params.append(department)
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            def scalar(sql, values=()):
                return conn.execute(sql, values).fetchone()[0]
            total = scalar("SELECT COUNT(*) FROM complaints" + where, params)
            resolved = scalar("SELECT COUNT(*) FROM complaints" + where + (" AND " if where else " WHERE ") + "lower(status) IN ('resolved','pilot deployed','closed')", params)
            active = scalar("SELECT COUNT(*) FROM complaints" + where + (" AND " if where else " WHERE ") + "lower(status) NOT IN ('resolved','pilot deployed','closed','rejected')", params)
            proposals = scalar("SELECT COUNT(*) FROM proposals")
            accepted_proposals = scalar("SELECT COUNT(*) FROM proposals WHERE lower(status) IN ('approved','accepted','endorsed')")
            sponsors = scalar("SELECT COUNT(*) FROM sponsorships")
            funds = scalar("SELECT COALESCE(SUM(pledge_amount),0) FROM sponsorships WHERE lower(status) NOT IN ('rejected','cancelled')")
            funding_status = [dict(r) for r in conn.execute("SELECT COALESCE(NULLIF(status,''),'unspecified') label, COUNT(*) count, ROUND(COALESCE(SUM(pledge_amount),0),2) amount FROM sponsorships GROUP BY COALESCE(NULLIF(status,''),'unspecified') ORDER BY amount DESC")]
            reviews = conn.execute("SELECT COUNT(*) n, COALESCE(ROUND(AVG(rating),2),0) rating, COALESCE(ROUND(AVG(impact_score),2),0) impact FROM reviews").fetchone()
            by_status = [dict(r) for r in conn.execute("SELECT status label, COUNT(*) value FROM complaints" + where + " GROUP BY status ORDER BY value DESC", params)]
            by_department = [dict(r) for r in conn.execute("SELECT COALESCE(NULLIF(department,''),'Unassigned') label, COUNT(*) value FROM complaints" + where + " GROUP BY department ORDER BY value DESC LIMIT 10", params)]
            by_priority = [dict(r) for r in conn.execute("SELECT COALESCE(NULLIF(priority,''),'Unspecified') label, COUNT(*) value FROM complaints" + where + " GROUP BY priority ORDER BY value DESC", params)]
            monthly = [dict(r) for r in conn.execute("SELECT substr(created_at,1,7) label, COUNT(*) value FROM complaints" + where + (" AND " if where else " WHERE ") + "created_at IS NOT NULL AND length(created_at)>=7 GROUP BY substr(created_at,1,7) ORDER BY label DESC LIMIT 12", params)][::-1]
            districts = [dict(r) for r in conn.execute("SELECT COALESCE(NULLIF(trim(district),''),'Unspecified') label, COUNT(*) value FROM complaints" + where + " GROUP BY label ORDER BY value DESC LIMIT 15", params)]
            task_rows = {r['status']: r['n'] for r in conn.execute("SELECT status, COUNT(*) n FROM collaboration_tasks GROUP BY status")}
            milestone_rows = {r['status']: r['n'] for r in conn.execute("SELECT status, COUNT(*) n FROM milestones GROUP BY status")}
            university_count = scalar("SELECT COUNT(*) FROM university_profiles")
            return {
                'generated_at': datetime.now().isoformat(), 'total_challenges': total,
                'resolved_challenges': resolved, 'active_challenges': active,
                'resolution_rate': round((resolved / total) * 100, 2) if total else 0,
                'resolution_definition': "Resolved, Pilot Deployed, and Closed statuses divided by all filtered challenges; Rejected is not counted as resolved.",
                'filters': {'date_from': date_from, 'date_to': date_to, 'district': district, 'department': department},
                'filtered_metrics': ['total_challenges','resolved_challenges','active_challenges','resolution_rate','by_status','by_department','by_priority','monthly_trend','by_district'],
                'non_complaint_metrics_scope': 'All-time totals; not filtered by complaint date, district, or department.',
                'total_proposals': proposals, 'accepted_proposals': accepted_proposals,
                'proposal_acceptance_rate': round((accepted_proposals / proposals) * 100, 2) if proposals else 0,
                'sponsorship_count': sponsors, 'pledged_funding': round(float(funds or 0), 2), 'funding_by_status': funding_status,
                'review_count': reviews['n'], 'average_rating': reviews['rating'], 'average_impact_score': reviews['impact'],
                'university_profiles': university_count, 'by_status': by_status,
                'by_department': by_department, 'by_priority': by_priority, 'monthly_trend': monthly,
                'by_district': districts, 'tasks_by_status': task_rows, 'milestones_by_status': milestone_rows
            }
        finally:
            conn.close()


def add_complaint_status_event(complaint_id, old_status, new_status, actor_user_id="", actor_name="", actor_role="", note=""):
    """Persist a status transition event for a complaint."""
    with _lock:
        conn = _connect()
        try:
            conn.execute("INSERT INTO complaint_status_history (complaint_id, old_status, new_status, actor_user_id, actor_name, actor_role, note, changed_at) VALUES (?,?,?,?,?,?,?,?)",
                         (complaint_id, old_status, new_status, actor_user_id or "", actor_name or "", actor_role or "", (note or "")[:500], datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()


def get_complaint_status_history(complaint_id):
    """Return public-safe status history; never expose actor identity or internal notes."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT old_status, new_status, changed_at, note FROM complaint_status_history WHERE complaint_id=? ORDER BY id ASC", (complaint_id,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def get_complaints_by_owner(owner_user_id, page=1, per_page=100):
    """Return only complaints linked to this authenticated account."""
    page = max(1, int(page))
    per_page = max(1, min(100, int(per_page)))
    with _lock:
        conn = _connect()
        try:
            total = conn.execute("SELECT COUNT(*) AS c FROM complaints WHERE owner_user_id=?", (owner_user_id,)).fetchone()["c"]
            rows = conn.execute(
                "SELECT * FROM complaints WHERE owner_user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (owner_user_id, per_page, (page - 1) * per_page),
            ).fetchall()
            return [dict(r) for r in rows], total
        finally:
            conn.close()


def claim_due_notifications(limit=25):
    """Claim due notifications for a single worker; returns claimed rows."""
    now = datetime.now().isoformat()
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            stale_before = datetime.fromtimestamp(datetime.now().timestamp() - 600).isoformat()
            rows = conn.execute(
                "SELECT * FROM notification_outbox WHERE "
                "((status IN ('pending','failed') AND next_attempt_at<=?) OR (status='processing' AND updated_at<=?)) "
                "AND attempts<8 ORDER BY id LIMIT ?", (now, stale_before, max(1, min(int(limit), 100)))
            ).fetchall()
            ids = [r['id'] for r in rows]
            if ids:
                placeholders = ','.join('?' for _ in ids)
                conn.execute(f"UPDATE notification_outbox SET status='processing', updated_at=? WHERE id IN ({placeholders})", [now] + ids)
            conn.commit()
            return [dict(r) for r in rows]
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def finish_notification(notification_id, success, error='', delivery_mode='unknown'):
    now = datetime.now().isoformat()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT attempts FROM notification_outbox WHERE id=?", (notification_id,)).fetchone()
            if row is None:
                return False
            attempts = int(row['attempts']) + 1
            if success:
                conn.execute("UPDATE notification_outbox SET status='sent', attempts=?, sent_at=?, updated_at=?, delivery_mode=?, last_error='' WHERE id=?",
                             (attempts, now, now, delivery_mode, notification_id))
            else:
                # Exponential retry delay, capped at six hours. Stop after eight attempts.
                delay_seconds = min(21600, 60 * (2 ** min(attempts - 1, 9)))
                status = 'failed' if attempts >= 8 else 'pending'
                retry_at = datetime.fromtimestamp(datetime.now().timestamp() + delay_seconds).isoformat()
                conn.execute("UPDATE notification_outbox SET status=?, attempts=?, updated_at=?, next_attempt_at=?, last_error=? WHERE id=?",
                             (status, attempts, now, retry_at, (error or 'Delivery failed')[:500], notification_id))
            conn.commit()
            return True
        finally:
            conn.close()
