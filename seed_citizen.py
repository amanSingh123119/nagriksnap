import sys
import os
import sqlite3
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
import backend.database as db
from backend.main import hash_password

pwd_hash = hash_password('Password123!')
now = datetime.now().isoformat()

conn = sqlite3.connect('backend/nagriksnap.db')
c = conn.cursor()

# 1. Update existing citizen aman.2710.singh.1947@gmail.com password to Password123!
c.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pwd_hash, 'aman.2710.singh.1947@gmail.com'))
print("Updated aman.2710.singh.1947@gmail.com password to Password123!")

# 2. Check or create demo.citizen@example.test
citizen_user = db.get_user_by_email('demo.citizen@example.test')
if not citizen_user:
    citizen_id = f"U-{uuid.uuid4().hex.upper()}"
    c.execute("""
        INSERT INTO users (id, name, username, phone, email, password_hash, role, organization, department, address, lat, lng, created_at, updated_at, last_login)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        citizen_id,
        'Demo Citizen',
        'demo_citizen',
        '+919876543210',
        'demo.citizen@example.test',
        pwd_hash,
        'citizen',
        '',
        '',
        'Connaught Place, New Delhi',
        28.6315,
        77.2167,
        now,
        now,
        now
    ))
    print("Created demo citizen account demo.citizen@example.test")
    citizen_user = {'id': citizen_id}
else:
    c.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pwd_hash, 'demo.citizen@example.test'))
    print("Updated demo citizen password")

conn.commit()

# 3. Fetch citizen ids
c.execute("SELECT id FROM users WHERE email IN ('demo.citizen@example.test', 'aman.2710.singh.1947@gmail.com')")
citizen_ids = [row[0] for row in c.fetchall()]

# 4. Ensure some complaints are linked to these citizens so the citizen dashboard displays cards, charts, and table
sample_issues = [
    {
        "id": "CMP-2026-101",
        "title": "Severe Potholes and Waterlogging on Main Market Road",
        "description": "Road surface completely degraded causing daily traffic snarls and two-wheeler accidents near Sector 4.",
        "phone": "+919876543210",
        "address": "Sector 4 Main Market, Near Metro Gate 2",
        "lat": 28.6289,
        "lng": 77.2180,
        "department": "Public Works / Roads",
        "category": "Roads & Footpaths",
        "status": "In Progress",
        "created_at": "2026-09-24 10:30:00"
    },
    {
        "id": "CMP-2026-102",
        "title": "Broken Streetlights along Park Avenue",
        "description": "Cluster of 6 LED streetlights non-functional for past 2 weeks creating safety concern after dark.",
        "phone": "+919876543210",
        "address": "Park Avenue Block C",
        "lat": 28.6350,
        "lng": 77.2150,
        "department": "Electrical / Street Lights",
        "category": "Street Lighting",
        "status": "Assigned",
        "created_at": "2026-09-25 14:15:00"
    },
    {
        "id": "CMP-2026-103",
        "title": "Uncollected Garbage Accumulation near Community Center",
        "description": "Municipal bin overflowing for 4 days attracting stray animals and blocking sidewalk.",
        "phone": "+919876543210",
        "address": "Civil Lines Ward 12",
        "lat": 28.6320,
        "lng": 77.2210,
        "department": "Sanitation / Waste Management",
        "category": "Solid Waste",
        "status": "Resolved",
        "created_at": "2026-09-20 09:00:00"
    },
    {
        "id": "CMP-2026-104",
        "title": "Low Water Pressure and Pipeline Leakage",
        "description": "Fresh drinking water pipeline leaking onto the road, residents receiving muddy water at low pressure.",
        "phone": "+919876543210",
        "address": "Subhash Nagar Lane 3",
        "lat": 28.6270,
        "lng": 77.2120,
        "department": "Water Supply",
        "category": "Water Distribution",
        "status": "Pending",
        "created_at": "2026-09-27 16:45:00"
    },
    {
        "id": "CMP-2026-105",
        "title": "Open Manhole Danger near Government Primary School",
        "description": "Missing cast-iron manhole cover poses imminent hazard to school children and commuters.",
        "phone": "+919876543210",
        "address": "School Road, Model Town",
        "lat": 28.6365,
        "lng": 77.2240,
        "department": "Drainage / Sewerage",
        "category": "Drainage",
        "status": "Under Review",
        "created_at": "2026-09-28 08:20:00"
    }
]

for citizen_id in citizen_ids:
    for idx, iss in enumerate(sample_issues):
        comp_id = f"{iss['id']}-{citizen_id[:4]}"
        c.execute("SELECT id FROM complaints WHERE id = ?", (comp_id,))
        if not c.fetchone():
            c.execute("""
                INSERT INTO complaints (
                    id, title, description, phone, address, lat, lng,
                    department, category, sdg_tag, priority, status,
                    bounty_amount, created_at, owner_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                comp_id,
                iss["title"],
                iss["description"],
                iss["phone"],
                iss["address"],
                iss["lat"],
                iss["lng"],
                iss["department"],
                iss["category"],
                "SDG 11 - Sustainable Cities",
                "High",
                iss["status"],
                0.0,
                iss["created_at"],
                citizen_id
            ))
            print(f"Added sample complaint {comp_id} for citizen {citizen_id}")

conn.commit()
conn.close()
print("All citizen accounts and sample issues successfully seeded!")
