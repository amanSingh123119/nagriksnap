import sys
import os
import sqlite3

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.main import hash_password

new_hash = hash_password('Password123!')
conn = sqlite3.connect('backend/nagriksnap.db')
emails = ('demo.govt@example.test', 'demo.university@example.test', 'demo.industry@example.test', 'demo.admin@example.test', 'demo.citizen@example.test', 'aman.2710.singh.1947@gmail.com')
placeholders = ', '.join(['?'] * len(emails))
c.execute(f'UPDATE users SET password_hash = ? WHERE email IN ({placeholders})', (new_hash, *emails))
conn.commit()
print('Passwords updated to Password123!')
