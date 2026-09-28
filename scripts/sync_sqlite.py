import sqlite3
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from main import hash_password

pwd_hash = hash_password('Password123!')
now = datetime.now().isoformat()

conn = sqlite3.connect('backend/nagriksnap.db')
c = conn.cursor()

accounts = [
    ('U-GOVT-001', 'Rakesh Sharma (Nodal Officer)', 'government', '9876540001', 'demo.government@example.test', pwd_hash, 'govt_admin', 'Municipal Corporation', 'Public Works / Roads'),
    ('U-GOVT-002', 'Rakesh Sharma', 'govt', '9876540002', 'demo.govt@example.test', pwd_hash, 'govt_admin', 'Municipal Corporation', 'Public Works / Roads'),
    ('U-IND-001', 'Amit Verma (CSR Director)', 'industry', '9876540003', 'demo.industry@example.test', pwd_hash, 'industry', 'TechNova Solutions Ltd.', 'CSR Foundation'),
    ('U-UNIV-001', 'Prof. Rajesh Iyer (Research Dean)', 'university', '9876540004', 'demo.university@example.test', pwd_hash, 'university', 'Apex Engineering Institute', 'Computer Science & Engineering'),
    ('U-ADM-001', 'Central Platform Administrator', 'admin', '9876540005', 'demo.admin@example.test', pwd_hash, 'admin', 'Smart City Innovation Mission', 'System Operations'),
    ('U-CIT-001', 'Demo Citizen', 'citizen', '9876540006', 'demo.citizen@example.test', pwd_hash, 'citizen', '', ''),
    ('U-CIT-002', 'Aman Singh', 'aman_singh89', '9876540007', 'aman.2710.singh.1947@gmail.com', pwd_hash, 'citizen', '', '')
]

for uid, name, uname, phone, email, phash, role, org, dept in accounts:
    c.execute('SELECT id FROM users WHERE lower(email)=lower(?) OR lower(username)=lower(?)', (email, uname))
    row = c.fetchone()
    if row:
        c.execute('UPDATE users SET name=?, username=?, email=?, password_hash=?, role=?, organization=?, department=?, updated_at=? WHERE id=?',
                  (name, uname, email, phash, role, org, dept, now, row[0]))
    else:
        c.execute('INSERT INTO users (id, name, username, phone, email, password_hash, role, organization, department, address, lat, lng, created_at, updated_at, last_login) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                  (uid, name, uname, phone, email, phash, role, org, dept, 'National Capital Region', 28.6139, 77.2090, now, now, now))

conn.commit()
conn.close()
print('SQLite accounts synchronized!')
