import sys
import os
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import database as db
from main import hash_password

pwd_hash = hash_password('Password123!')
now = datetime.now().isoformat()

# The clean target accounts for every role:
target_accounts = [
    # 1. Government Officers (Support both demo.govt and demo.government, plus username 'govt' and 'government')
    {
        'id': 'U-GOVT-001',
        'name': 'Rakesh Sharma (Nodal Officer)',
        'username': 'govt',
        'email': 'demo.government@example.test',
        'phone': '9876540001',
        'role': 'govt_admin',
        'organization': 'Municipal Corporation',
        'department': 'Public Works / Roads'
    },
    {
        'id': 'U-GOVT-002',
        'name': 'Rakesh Sharma',
        'username': 'government',
        'email': 'demo.govt@example.test',
        'phone': '9876540002',
        'role': 'govt_admin',
        'organization': 'Municipal Corporation',
        'department': 'Public Works / Roads'
    },
    # 2. Industry CSR Partners (Support username 'industry' and 'demo.industry@example.test')
    {
        'id': 'U-IND-001',
        'name': 'Amit Verma (CSR Director)',
        'username': 'industry',
        'email': 'demo.industry@example.test',
        'phone': '9876540003',
        'role': 'industry',
        'organization': 'TechNova Solutions Ltd.',
        'department': 'CSR Foundation'
    },
    # 3. University Innovators (Support username 'university' and 'demo.university@example.test')
    {
        'id': 'U-UNIV-001',
        'name': 'Prof. Rajesh Iyer (Research Dean)',
        'username': 'university',
        'email': 'demo.university@example.test',
        'phone': '9876540004',
        'role': 'university',
        'organization': 'Apex Engineering Institute',
        'department': 'Computer Science & Engineering'
    },
    # 4. Central Platform Administrators (Support username 'admin' and 'demo.admin@example.test')
    {
        'id': 'U-ADM-001',
        'name': 'Central Platform Administrator',
        'username': 'admin',
        'email': 'demo.admin@example.test',
        'phone': '9876540005',
        'role': 'admin',
        'organization': 'Smart City Innovation Mission',
        'department': 'System Operations'
    },
    # 5. Citizens (Support username 'citizen', 'demo.citizen@example.test', and Aman Singh)
    {
        'id': 'U-CIT-001',
        'name': 'Demo Citizen',
        'username': 'citizen',
        'email': 'demo.citizen@example.test',
        'phone': '9876540006',
        'role': 'citizen',
        'organization': '',
        'department': ''
    },
    {
        'id': 'U-CIT-002',
        'name': 'Aman Singh',
        'username': 'aman_singh89',
        'email': 'aman.2710.singh.1947@gmail.com',
        'phone': '9876540007',
        'role': 'citizen',
        'organization': '',
        'department': ''
    }
]

print(f"Connecting to database (Postgres mode: {getattr(db, 'IS_POSTGRES', False)})...")

with db._lock:
    conn = db._connect()
    try:
        for acc in target_accounts:
            # Check existing by email
            row = conn.execute("SELECT id FROM users WHERE lower(email)=lower(?) LIMIT 1", (acc['email'],)).fetchone()
            if not row:
                row = conn.execute("SELECT id FROM users WHERE lower(username)=lower(?) LIMIT 1", (acc['username'],)).fetchone()
            
            if row:
                uid = row['id']
                conn.execute("""
                    UPDATE users
                    SET name = ?, username = ?, email = ?, password_hash = ?, role = ?, organization = ?, department = ?, updated_at = ?
                    WHERE id = ?
                """, (acc['name'], acc['username'], acc['email'], pwd_hash, acc['role'], acc['organization'], acc['department'], now, uid))
                print(f"  [UPDATED] {acc['role']}: {acc['username']} | {acc['email']}")
            else:
                conn.execute("""
                    INSERT INTO users (id, name, username, phone, email, password_hash, role, organization, department, address, lat, lng, created_at, updated_at, last_login)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    acc['id'], acc['name'], acc['username'], acc['phone'], acc['email'],
                    pwd_hash, acc['role'], acc['organization'], acc['department'],
                    'National Capital Region', 28.6139, 77.2090, now, now, now
                ))
                print(f"  [CREATED] {acc['role']}: {acc['username']} | {acc['email']}")
        
        conn.commit()
    finally:
        conn.close()

print("\nSUCCESS: All accounts provisioned and synced with password 'Password123!'")
