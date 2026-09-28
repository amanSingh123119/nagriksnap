"""Create a privileged workspace account in the local database."""

import argparse
from datetime import datetime
from getpass import getpass
import re
import secrets
import uuid

import database as db
from main import hash_password


PROVISIONABLE_ROLES = ("admin", "govt_admin", "university", "industry")


def create_provisioned_user(*, name, email, phone, role, password, organization="", department=""):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    phone = (phone or "").strip()
    organization = (organization or "").strip()
    department = (department or "").strip()

    if role not in PROVISIONABLE_ROLES:
        raise ValueError("Choose admin, govt_admin, university, or industry.")
    if not name:
        raise ValueError("Name is required.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")
    if not re.fullmatch(r"[+0-9 ()-]{8,20}", phone):
        raise ValueError("Enter a valid phone number.")
    if len(password or "") < 10:
        raise ValueError("Password must be at least 10 characters.")
    if role in {"university", "industry"} and not organization:
        raise ValueError("Organization is required for university and industry accounts.")

    existing_users = db.get_users()
    if db.get_user_by_email(email):
        raise ValueError("An account with this email already exists.")
    if any(str(user.get("phone", "")) == phone for user in existing_users):
        raise ValueError("An account with this phone number already exists.")

    username_base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "user"
    username = f"{username_base}_{secrets.token_hex(3)}"
    now = datetime.now().isoformat()
    user = {
        "id": f"U-{uuid.uuid4().hex.upper()}",
        "name": name,
        "username": username,
        "phone": phone,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "organization": organization,
        "department": department,
        "address": "",
        "lat": None,
        "lng": None,
        "created_at": now,
        "updated_at": now,
        "last_login": "",
    }
    db.add_user(user)
    return {"id": user["id"], "username": username, "role": role}


def main():
    parser = argparse.ArgumentParser(description="Provision a privileged NagrikSnap workspace account.")
    parser.add_argument("--role", choices=PROVISIONABLE_ROLES, required=True)
    args = parser.parse_args()

    password = getpass("New account password (10+ characters): ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")

    try:
        account = create_provisioned_user(
            name=input("Full name: "),
            email=input("Email: "),
            phone=input("Phone: "),
            role=args.role,
            password=password,
            organization=input("Organization (required for university/industry): "),
            department=input("Department (optional): "),
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    print(f"Created {account['role']} account. Sign in with its email or phone number.")


if __name__ == "__main__":
    main()