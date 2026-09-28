import sys
import os
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import database as db
from main import hash_password

pwd_hash = hash_password('Password123!')
now = datetime.now().isoformat()

accounts = [
    # Government
    {
        'id': 'GOVT-ADMIN-PRIMARY',
        'name': 'Rakesh Sharma (Nodal Officer)',
        'username': 'government',
        'email': 'demo.government@example.test',
        'phone': '9876540001',
        'role': 'govt_admin',
        'organization': 'Municipal Corporation',
        'department': 'Public Works / Roads'
    },
    {
        'id': 'GOVT-ADMIN-ALIAS',
        'name': 'Rakesh Sharma',
        'username': 'govt',
        'email': 'demo.govt@example.test',
        'phone': '9876540002',
        'role': 'govt_admin',
        'organization': 'Municipal Corporation',
        'department': 'Public Works / Roads'
    },
    # Industry
    {
        'id': 'INDUSTRY-PRIMARY',
        'name': 'Amit Verma (CSR Director)',
        'username': 'industry',
        'email': 'demo.industry@example.test',
        'phone': '9876540003',
        'role': 'industry',
        'organization': 'TechNova Solutions Ltd.',
        'department': 'CSR Foundation'
    },
    # University
    {
        'id': 'UNIVERSITY-PRIMARY',
        'name': 'Prof. Rajesh Iyer (Research Dean)',
        'username': 'university',
        'email': 'demo.university@example.test',
        'phone': '9876540004',
        'role': 'university',
        'organization': 'Apex Engineering Institute',
        'department': 'Computer Science & Engineering'
    },
    # Nodal Admin / Super Admin
    {
        'id': 'ADMIN-PRIMARY',
        'name': 'Central Platform Administrator',
        'username': 'admin',
        'email': 'demo.admin@example.test',
        'phone': '9876540005',
        'role': 'admin',
        'organization': 'Smart City Innovation Mission',
        'department': 'System Operations'
    },
    # Citizen
    {
        'id': 'CITIZEN-PRIMARY',
        'name': 'Aman Singh',
        'username': 'citizen',
        'email': 'demo.citizen@example.test',
        'phone': '9876540006',
        'role': 'citizen',
        'organization': '',
        'department': ''
    },
    {
        'id': 'CITIZEN-USER',
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

conn = db._connect()
try:
    for acc in accounts:
        all_users = db.get_users()
        existing = db.get_user_by_email(acc['email']) or next((u for u in all_users if u.get('username') == acc['username']), None)
        if existing:
            conn.execute("""
                UPDATE users
                SET name = ?, username = ?, email = ?, password_hash = ?, role = ?, organization = ?, department = ?, updated_at = ?
                WHERE id = ?
            """, (
                acc['name'],
                acc['username'],
                acc['email'],
                pwd_hash,
                acc['role'],
                acc['organization'],
                acc['department'],
                now,
                existing['id']
            ))
            print(f"Updated account: {acc['username']} / {acc['email']} ({acc['role']})")
        else:
            conn.execute("""
                INSERT INTO users (id, name, username, phone, email, password_hash, role, organization, department, address, lat, lng, created_at, updated_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                acc['id'],
                acc['name'],
                acc['username'],
                acc['phone'],
                acc['email'],
                pwd_hash,
                acc['role'],
                acc['organization'],
                acc['department'],
                'National Capital Region',
                28.6139,
                77.2090,
                now,
                now,
                now
            ))
            print(f"Created account: {acc['username']} / {acc['email']} ({acc['role']})")

    conn.commit()
finally:
    conn.close()

print("All friendly accounts successfully provisioned with password 'Password123!'")
