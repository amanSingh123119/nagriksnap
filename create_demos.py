import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
import backend.database as db
from backend.provision_user import create_provisioned_user

demo_users = [
    {'role': 'govt_admin', 'email': 'demo.govt@example.test', 'name': 'Rakesh Sharma', 'organization': 'Municipal Corporation Vadodara'},
    {'role': 'university', 'email': 'demo.university@example.test', 'name': 'Demo Univ', 'organization': 'Test Univ'},
    {'role': 'industry', 'email': 'demo.industry@example.test', 'name': 'Amit Verma', 'organization': 'TechNova Solutions Ltd.'},
    {'role': 'admin', 'email': 'demo.admin@example.test', 'name': 'Aman Kumar'}
]

for idx, u in enumerate(demo_users):
    if not db.get_user_by_email(u['email']):
        try:
            create_provisioned_user(
                name=u['name'],
                email=u['email'],
                phone=f'123456789{idx}',
                role=u['role'],
                password='Password123!',
                organization=u.get('organization', '')
            )
            print(f"Created {u['role']} account.")
        except Exception as e:
            print(f"Failed for {u['role']}: {e}")
    else:
        print(f"{u['role']} account already exists.")

# Ensure citizen demo account exists
if not db.get_user_by_email('demo.citizen@example.test'):
    import uuid, datetime
    from backend.main import hash_password
    now = datetime.datetime.now().isoformat()
    db.add_user({
        'id': f"U-{uuid.uuid4().hex.upper()}",
        'name': 'Demo Citizen',
        'username': 'demo_citizen',
        'phone': '+919876543210',
        'email': 'demo.citizen@example.test',
        'password_hash': hash_password('Password123!'),
        'role': 'citizen',
        'organization': '',
        'department': '',
        'address': 'New Delhi',
        'lat': 28.6139,
        'lng': 77.2090,
        'created_at': now,
        'updated_at': now,
        'last_login': now
    })
    print("Created citizen account.")
else:
    print("citizen account already exists.")
