"""Focused P0 security regression tests. Run: python -m unittest discover -s tests -v"""
import os
import tempfile
import unittest
from unittest.mock import patch

import database as db

# Isolate tests from any developer database.
_tmp = tempfile.TemporaryDirectory(prefix="nagriksnap-security-test-")
db.IS_POSTGRES = False
db.DATABASE_URL = ""
db.DB_PATH = os.path.join(_tmp.name, "test.db")
db.init_db()

import main
import provision_user
from fastapi.testclient import TestClient


class SecurityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def test_live_server_origin_is_allowed_for_auth_preflight(self):
        response = self.client.options("/auth/login", headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://127.0.0.1:5500")

    def test_collaboration_directory_search_returns_minimal_profile_fields(self):
        db.add_user({"id": "DIR-TEST-USER", "name": "Directory Test Faculty", "username": "dirfaculty",
                     "phone": "private-phone", "role": "faculty", "organization": "Test University",
                     "department": "Civil Engineering"})
        results = db.search_collaboration_users("Directory Test", "ANOTHER-USER", 20)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "DIR-TEST-USER")
        self.assertEqual(results[0]["organization"], "Test University")
        self.assertNotIn("phone", results[0])
        self.assertNotIn("password_hash", results[0])
        self.assertEqual(db.search_collaboration_users("D", "ANOTHER-USER", 20), [])

    @patch("database.consume_rate_limit", return_value=True)
    def test_provisioned_workspace_accounts_can_log_in(self, _rate_limit):
        roles = ("admin", "govt_admin", "university", "industry")
        for index, role in enumerate(roles):
            email = f"{role}@provision-test.example"
            password = "Provisioned-Password-2026"
            provision_user.create_provisioned_user(
                name=f"Provisioned {role}", email=email, phone=f"+9198765401{index:02d}",
                role=role, password=password, organization="Test Organization"
            )
            response = self.client.post("/auth/login", json={"username": email, "password": password})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["role"], role)

    @patch("database.consume_rate_limit", return_value=True)
    def test_environment_provisioned_admin_has_admin_role(self, _rate_limit):
        password = "Environment-Admin-Password-2026"
        with patch.object(main, "ADMIN_USERNAME", "environment-admin"), \
             patch.object(main, "ADMIN_PASSWORD_HASH", main.hash_password(password)):
            response = self.client.post("/auth/login", json={
                "username": "environment-admin", "password": password
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["role"], "admin")

    @patch("database.consume_rate_limit", return_value=True)
    def test_development_demo_login_is_limited_to_provisioned_roles(self, _rate_limit):
        roles = ("admin", "govt_admin", "university", "industry")
        demo_emails = {
            "admin": "demo.admin@example.test",
            "govt_admin": "demo.govt@example.test",
            "university": "demo.university@example.test",
            "industry": "demo.industry@example.test",
        }
        for index, role in enumerate(roles):
            provision_user.create_provisioned_user(
                name=f"Demo {role}", email=demo_emails[role],
                phone=f"+9198765402{index:02d}", role=role,
                password="Demo-Workspace-2026!", organization="Demo Organization"
            )

        with patch.object(main, "APP_ENV", "development"):
            for role in roles:
                response = self.client.post("/auth/demo-login", json={"role": role})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["role"], role)

    @patch("database.consume_rate_limit", return_value=True)
    def test_demo_login_is_disabled_outside_development(self, _rate_limit):
        with patch.object(main, "APP_ENV", "staging"):
            response = self.client.post("/auth/demo-login", json={"role": "admin"})
        self.assertEqual(response.status_code, 404)

    @patch("database.consume_rate_limit", return_value=True)
    def test_successful_login_attempts_email_notification(self, _rate_limit):
        registered = self.client.post("/auth/register", json={
            "name": "Login Notice Test", "phone": "+919876549003", "email": "login-notice@example.test",
            "password": "Old-Password-2026-Long"
        })
        self.assertEqual(registered.status_code, 200, registered.text)
        with patch.object(main, "send_email", return_value=True) as send:
            response = self.client.post("/auth/login", json={
                "username": "login-notice@example.test", "password": "Old-Password-2026-Long"
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(send.called)
        self.assertEqual(send.call_args.args[0], "login-notice@example.test")

    @patch("database.consume_rate_limit", return_value=True)
    def test_email_password_reset_changes_password_and_revokes_sessions(self, _rate_limit):
        registered = self.client.post("/auth/register", json={
            "name": "Reset Test", "phone": "+919876549001", "email": "reset@example.test",
            "password": "Old-Password-2026-Long"
        })
        self.assertEqual(registered.status_code, 200, registered.text)
        old_token = registered.json()["token"]
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.test", "SMTP_FROM": "noreply@example.test"}), \
             patch.object(main, "send_email", return_value=True) as send:
            requested = self.client.post("/auth/password-reset/request", json={"email": "reset@example.test"})
        self.assertEqual(requested.status_code, 200, requested.text)
        self.assertTrue(send.called)
        reset_id = requested.json()["reset_id"]
        # The test mailer is mocked; read only the hash record and replace it with a known OTP hash.
        import hashlib
        record = db.get_password_reset_token(reset_id)
        self.assertIsNotNone(record)
        known_otp = "123456"
        with db._lock:
            conn = db._connect()
            try:
                conn.execute("UPDATE password_reset_tokens SET token_hash=? WHERE id=?",
                             (hashlib.sha256(known_otp.encode()).hexdigest(), reset_id))
                conn.commit()
            finally:
                conn.close()
        confirmed = self.client.post("/auth/password-reset/confirm", json={
            "reset_id": reset_id, "otp": known_otp, "new_password": "New-Password-2026-Long"
        })
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(self.client.get("/api/me/complaints", headers={"Authorization": f"Bearer {old_token}"}).status_code, 401)
        login = self.client.post("/auth/login", json={"username": "reset@example.test", "password": "New-Password-2026-Long"})
        self.assertEqual(login.status_code, 200, login.text)

    @patch("database.consume_rate_limit", return_value=True)
    def test_password_reset_otp_is_single_use(self, _rate_limit):
        registered = self.client.post("/auth/register", json={
            "name": "Reset Test Two", "phone": "+919876549002", "email": "reset2@example.test",
            "password": "Old-Password-2026-Long"
        })
        self.assertEqual(registered.status_code, 200, registered.text)
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.test", "SMTP_FROM": "noreply@example.test"}), \
             patch.object(main, "send_email", return_value=True):
            requested = self.client.post("/auth/password-reset/request", json={"email": "reset2@example.test"})
        reset_id = requested.json()["reset_id"]
        import hashlib
        with db._lock:
            conn = db._connect()
            try:
                conn.execute("UPDATE password_reset_tokens SET token_hash=? WHERE id=?",
                             (hashlib.sha256(b"654321").hexdigest(), reset_id))
                conn.commit()
            finally:
                conn.close()
        payload = {"reset_id": reset_id, "otp": "654321", "new_password": "New-Password-2026-Long"}
        self.assertEqual(self.client.post("/auth/password-reset/confirm", json=payload).status_code, 200)
        self.assertEqual(self.client.post("/auth/password-reset/confirm", json=payload).status_code, 400)


    def test_cross_role_workflow_writes_require_authorized_roles(self):
        citizen_token = main.create_token("citizen-test", "citizen", "CIT-ROLE-TEST")
        headers = {"Authorization": f"Bearer {citizen_token}"}
        proposal = self.client.post("/api/challenges/UNKNOWN/proposals", headers=headers, json={
            "challenge_id": "UNKNOWN", "team_name": "Team", "university_name": "Example University",
            "lead_name": "Lead", "lead_email": "lead@example.test", "abstract": "A solution"
        })
        sponsorship = self.client.post("/api/challenges/UNKNOWN/sponsor", headers=headers, json={
            "challenge_id": "UNKNOWN", "company_name": "Example Company", "contact_name": "Contact",
            "contact_email": "contact@example.test", "pledge_amount": 1000
        })
        self.assertEqual(proposal.status_code, 403)
        self.assertEqual(sponsorship.status_code, 403)

    def test_university_profile_requires_bearer_token(self):
        self.assertEqual(self.client.get("/api/university/profile").status_code, 401)

    def test_sensitive_routes_require_authentication(self):
        paths = [
            ("GET", "/api/challenges/CH-2026-ABCDEF/case-room"),
            ("GET", "/api/challenges/CH-2026-ABCDEF/proposals"),
            ("GET", "/api/challenges/CH-2026-ABCDEF/sponsorships"),
            ("GET", "/api/challenges/CH-2026-ABCDEF/milestones"),
            ("GET", "/api/admin/audit-logs"),
            ("GET", "/uploads/CH-2026-ABCDEF_deadbeef.jpg"),
            ("POST", "/api/ai-match"),
        ]
        for method, path in paths:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path, json={} if method == "POST" else None)
                self.assertEqual(response.status_code, 401)

    def test_registration_cannot_escalate_role_or_claim_organization(self):
        response = self.client.post("/auth/register", json={
            "name": "Regression Citizen", "phone": "+919876540001",
            "email": "test-9876540001@example.test",
            "password": "A-Long-Test-Password-2026", "role": "admin",
            "organization": "Pretend University"
        })
        self.assertEqual(response.status_code, 200)
        user = response.json()["user"]
        self.assertEqual(user["role"], "citizen")
        self.assertEqual(user["organization"], "")

    def test_citizen_cannot_enter_case_room(self):
        response = self.client.post("/auth/register", json={
            "name": "Regression Citizen 2", "phone": "+919876540002",
            "email": "test-9876540002@example.test",
            "password": "A-Long-Test-Password-2026"
        })
        token = response.json()["token"]
        denied = self.client.get("/api/challenges/CH-2026-001/case-room",
                                 headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(denied.status_code, 403)

    def test_my_complaints_is_account_scoped_and_requires_citizen_auth(self):
        first = self.client.post("/auth/register", json={
            "name": "Owner One", "phone": "+919876541101", "password": "Owner-One-Password-2026",
            "email": "test-9876541101@example.test",
        }).json()
        second = self.client.post("/auth/register", json={
            "name": "Owner Two", "phone": "+919876541102", "password": "Owner-Two-Password-2026",
            "email": "test-9876541102@example.test",
        }).json()
        db.add_complaint({
            "id": "CH-OWNED-ONE", "title": "Owned report", "description": "Account scoped test",
            "phone": "+919876541101", "status": "Crowdsourced", "owner_user_id": first["user"]["id"],
            "created_at": "2026-09-27T00:00:00"
        })
        self.assertEqual(self.client.get("/api/me/complaints").status_code, 401)
        first_result = self.client.get("/api/me/complaints", headers={"Authorization": f"Bearer {first['token']}"})
        second_result = self.client.get("/api/me/complaints", headers={"Authorization": f"Bearer {second['token']}"})
        self.assertEqual(first_result.status_code, 200)
        self.assertEqual([c["id"] for c in first_result.json()["complaints"]], ["CH-OWNED-ONE"])
        self.assertEqual(second_result.status_code, 200)
        self.assertEqual(second_result.json()["complaints"], [])
        self.assertNotIn("phone", first_result.json()["complaints"][0])

    def test_status_history_endpoint_returns_status_events_without_actor_identity(self):
        db.add_complaint({
            "id": "CH-HISTORY-001", "title": "History test", "description": "History test report",
            "phone": "+919876543210", "status": "Crowdsourced", "created_at": "2026-09-27T00:00:00"
        })
        db.add_complaint_status_event("CH-HISTORY-001", "Crowdsourced", "Under Review",
                                      actor_user_id="private-user", actor_name="Private Reviewer",
                                      actor_role="govt_admin", note="Status updated by an authorized reviewer")
        response = self.client.get("/api/challenges/CH-HISTORY-001/status-history")
        self.assertEqual(response.status_code, 200)
        history = response.json()["history"]
        self.assertEqual([event["new_status"] for event in history], ["Crowdsourced", "Under Review"])
        self.assertNotIn("actor_user_id", history[-1])
        self.assertNotIn("actor_name", history[-1])
        self.assertNotIn("actor_role", history[-1])
        self.assertEqual(self.client.get("/api/challenges/CH-NOT-FOUND/status-history").status_code, 404)

    def test_status_update_and_history_are_atomic(self):
        db.add_complaint({
            "id": "CH-ATOMIC-001", "title": "Atomic test", "description": "Transaction test",
            "status": "Crowdsourced", "created_at": "2026-09-27T00:00:00"
        })
        result = db.update_complaint_status_atomic(
            "CH-ATOMIC-001", {"status": "Under Review", "assigned_team_name": "Roads Team"},
            actor_user_id="reviewer-1", actor_name="Reviewer", actor_role="govt_admin",
            note="Atomic transition test"
        )
        self.assertEqual(result["old_status"], "Crowdsourced")
        self.assertTrue(result["status_changed"])
        self.assertEqual(db.get_complaint_by_id("CH-ATOMIC-001")["status"], "Under Review")
        history = db.get_complaint_status_history("CH-ATOMIC-001")
        self.assertEqual(history[-1]["new_status"], "Under Review")

    def test_failed_history_insert_rolls_back_status_update(self):
        db.add_complaint({
            "id": "CH-ATOMIC-FAIL", "title": "Rollback test", "description": "Transaction rollback",
            "status": "Crowdsourced", "created_at": "2026-09-27T00:00:00"
        })
        conn = db._connect()
        try:
            conn.execute("""CREATE TRIGGER fail_verified_history BEFORE INSERT ON complaint_status_history
                WHEN NEW.complaint_id='CH-ATOMIC-FAIL' AND NEW.new_status='Verified'
                BEGIN SELECT RAISE(ABORT, 'simulated history failure'); END""")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(Exception):
            db.update_complaint_status_atomic(
                "CH-ATOMIC-FAIL", {"status": "Verified"}, actor_user_id="reviewer-2",
                actor_name="Reviewer", actor_role="govt_admin"
            )
        self.assertEqual(db.get_complaint_by_id("CH-ATOMIC-FAIL")["status"], "Crowdsourced")
        history = db.get_complaint_status_history("CH-ATOMIC-FAIL")
        self.assertEqual([event["new_status"] for event in history], ["Crowdsourced"])

    def test_atomic_status_update_returns_none_for_unknown_complaint(self):
        self.assertIsNone(db.update_complaint_status_atomic("CH-MISSING-ATOMIC", {"status": "Verified"}))

    def test_public_challenge_detail_does_not_return_contact_or_assignment(self):
        db.add_complaint({
            "id": "CH-2026-SEC001", "title": "Test", "description": "Test description",
            "phone": "private-phone", "assigned_admin_id": "private-admin-id",
            "assigned_admin_name": "Private Admin", "status": "Crowdsourced",
            "created_at": "2026-01-01T00:00:00"
        })
        response = self.client.get("/api/challenges/CH-2026-SEC001")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for key in ("phone", "assigned_admin", "assigned_admin_id", "assigned_admin_name"):
            self.assertNotIn(key, body)

    def test_security_headers_present(self):
        response = self.client.get("/api/challenges")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")


    def test_organization_role_requires_admin_approval(self):
        citizen = self.client.post("/auth/register", json={
            "name": "Verification Applicant", "phone": "+919876540003",
            "email": "test-9876540003@example.test",
            "password": "A-Long-Test-Password-2026"
        })
        token = citizen.json()["token"]
        submitted = self.client.post("/api/organization-verification", headers={"Authorization": f"Bearer {token}"}, json={
            "requested_role": "university", "organization_name": "Example Technical University",
            "department": "Computer Science", "contact_email": "admin@example.edu",
            "website": "https://example.edu",
            "justification": "We are requesting a university account for verified faculty collaboration."
        })
        self.assertEqual(submitted.status_code, 200, submitted.text)
        request_id = submitted.json()["request"]["id"]
        # The submitted request does not change the user's permissions.
        self.assertEqual(main.verify_token(f"Bearer {token}")["role"], "citizen")

        db.add_user({"id":"TEST-ADMIN", "name":"Test Admin", "username":"test_admin", "phone":"+919876540099",
            "password_hash":main.hash_password("A-Long-Test-Password-2026"), "role":"govt_admin",
            "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        admin_token = main.create_token("test_admin", "govt_admin", "TEST-ADMIN")
        approved = self.client.post(f"/api/admin/organization-verification/{request_id}/review",
            headers={"Authorization": f"Bearer {admin_token}"}, json={"decision":"approved", "note":"Institution verified out of band."})
        self.assertEqual(approved.status_code, 200, approved.text)
        # Existing sessions read current role/org from the account, not stale claims.
        current = main.verify_token(f"Bearer {token}")
        self.assertEqual(current["role"], "university")
        self.assertEqual(current["organization"], "Example Technical University")

    def test_organization_verification_review_is_admin_only(self):
        citizen = self.client.post("/auth/register", json={
            "name": "Verification Applicant 2", "phone": "+919876540004",
            "email": "test-9876540004@example.test",
            "password": "A-Long-Test-Password-2026"
        })
        token = citizen.json()["token"]
        response = self.client.get("/api/admin/organization-verification", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)


    def test_rate_limit_is_shared_and_windowed_in_database(self):
        import hashlib
        bucket = hashlib.sha256(b"test-bucket").hexdigest()
        self.assertTrue(db.consume_rate_limit(bucket, 2, 60, now=1000))
        self.assertTrue(db.consume_rate_limit(bucket, 2, 60, now=1001))
        self.assertFalse(db.consume_rate_limit(bucket, 2, 60, now=1002))
        self.assertTrue(db.consume_rate_limit(bucket, 2, 60, now=1062))

    def test_university_profile_requires_verified_university_role(self):
        citizen = self.client.post("/auth/register", json={
            "name": "Profile Citizen", "phone": "+919876540020", "password": "A-Long-Test-Password-2026",
            "email": "test-9876540020@example.test",
        })
        token = citizen.json()["token"]
        response = self.client.put("/api/university/profile", headers={"Authorization": f"Bearer {token}"}, json={
            "expertise": "water IoT environmental engineering", "available_slots": 2
        })
        self.assertEqual(response.status_code, 403)
        read_response = self.client.get("/api/university/profile", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(read_response.status_code, 403)

    def test_university_profile_and_explainable_matching(self):
        db.add_user({"id":"TEST-UNI", "name":"Test University", "username":"test_uni", "phone":"+919876540021",
            "password_hash":main.hash_password("A-Long-Test-Password-2026"), "role":"university",
            "organization":"Test Water University", "department":"Engineering", "created_at":"2026-01-01T00:00:00"})
        uni_token = main.create_token("test_uni", "university", "TEST-UNI")
        saved = self.client.put("/api/university/profile", headers={"Authorization": f"Bearer {uni_token}"}, json={
            "expertise":"water IoT environmental engineering", "sdg_focus":"SDG 6 clean water",
            "past_projects":3, "available_slots":2, "districts":"New Delhi"
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["profile"]["available_slots"], 2)
        own_profile = self.client.get("/api/university/profile", headers={"Authorization": f"Bearer {uni_token}"})
        self.assertEqual(own_profile.status_code, 200, own_profile.text)
        self.assertEqual(own_profile.json()["profile"]["organization_name"], "Test Water University")
        db.add_user({"id":"TEST-ADMIN-MATCH", "name":"Match Admin", "username":"match_admin", "phone":"+919876540022",
            "password_hash":main.hash_password("A-Long-Test-Password-2026"), "role":"govt_admin",
            "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        admin_token = main.create_token("match_admin", "govt_admin", "TEST-ADMIN-MATCH")
        response = self.client.get("/api/challenges/CH-2026-001/matches", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["matches"])
        match = response.json()["matches"][0]
        self.assertEqual(match["organization_name"], "Test Water University")
        self.assertIn("reasons", match)
        self.assertIn("score", match)

    def test_p3_invitation_requires_acceptance_and_then_grants_scoped_access(self):
        db.add_user({"id":"P3-ADMIN", "name":"P3 Admin", "username":"p3_admin", "phone":"+919876541001",
            "password_hash":main.hash_password("A-Long-Test-Password-2026"), "role":"govt_admin",
            "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        db.add_user({"id":"P3-STUDENT", "name":"P3 Student", "username":"p3_student", "phone":"+919876541002",
            "password_hash":main.hash_password("A-Long-Test-Password-2026"), "role":"citizen",
            "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        admin_token = main.create_token("p3_admin", "govt_admin", "P3-ADMIN")
        student_token = main.create_token("p3_student", "citizen", "P3-STUDENT")
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        headers_student = {"Authorization": f"Bearer {student_token}"}
        invite = self.client.post("/api/challenges/CH-2026-001/collaboration/invitations", headers=headers_admin,
            json={"user_id":"P3-STUDENT", "member_role":"student"})
        self.assertEqual(invite.status_code, 200, invite.text)
        pending = self.client.get("/api/challenges/CH-2026-001/collaboration/tasks", headers=headers_student)
        self.assertEqual(pending.status_code, 403)
        accepted = self.client.post("/api/challenges/CH-2026-001/collaboration/invitations/decision", headers=headers_student,
            json={"decision":"accept"})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        tasks = self.client.get("/api/challenges/CH-2026-001/collaboration/tasks", headers=headers_student)
        self.assertEqual(tasks.status_code, 200, tasks.text)

    def test_p3_task_assignment_and_status_update_are_scoped(self):
        db.add_user({"id":"P3-ADMIN-T", "name":"Task Admin", "username":"p3_task_admin", "phone":"+919876541011",
            "password_hash":main.hash_password("A-Long-Test-Password-2026"), "role":"govt_admin",
            "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        db.add_user({"id":"P3-MEMBER-T", "name":"Task Member", "username":"p3_task_member", "phone":"+919876541012",
            "password_hash":main.hash_password("A-Long-Test-Password-2026"), "role":"citizen",
            "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        admin_token = main.create_token("p3_task_admin", "govt_admin", "P3-ADMIN-T")
        member_token = main.create_token("p3_task_member", "citizen", "P3-MEMBER-T")
        ha={"Authorization":f"Bearer {admin_token}"}; hm={"Authorization":f"Bearer {member_token}"}
        invite=self.client.post("/api/challenges/CH-2026-001/collaboration/invitations",headers=ha,json={"user_id":"P3-MEMBER-T","member_role":"student"})
        self.assertEqual(invite.status_code,200,invite.text)
        self.client.post("/api/challenges/CH-2026-001/collaboration/invitations/decision",headers=hm,json={"decision":"accept"})
        created=self.client.post("/api/challenges/CH-2026-001/collaboration/tasks",headers=hm,json={"title":"Prototype sensor node","priority":"high","assigned_to":"P3-MEMBER-T"})
        self.assertEqual(created.status_code,200,created.text)
        task_id=created.json()["task"]["id"]
        updated=self.client.patch(f"/api/collaboration/tasks/{task_id}",headers=hm,json={"status":"in_progress"})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()["task"]["status"],"in_progress")
        bad=self.client.patch(f"/api/collaboration/tasks/{task_id}",headers=hm,json={"status":"finished"})
        self.assertEqual(bad.status_code,422)

    def test_matching_endpoint_is_admin_only_and_missing_challenge_is_404(self):
        citizen = self.client.post("/auth/register", json={
            "name": "Match Citizen", "phone": "+919876540023", "password": "A-Long-Test-Password-2026",
            "email": "test-9876540023@example.test",
        })
        token = citizen.json()["token"]
        denied = self.client.get("/api/challenges/CH-2026-001/matches", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(denied.status_code, 403)


    def test_p4_impact_analytics_is_admin_only(self):
        denied = self.client.get("/api/admin/impact-analytics")
        self.assertEqual(denied.status_code, 401)
        citizen = self.client.post("/auth/register", json={
            "name": "Analytics Citizen", "phone": "+919876541111",
            "email": "test-9876541111@example.test",
            "password": "A-Long-Test-Password-2026"
        })
        token = citizen.json()["token"]
        denied = self.client.get("/api/admin/impact-analytics", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(denied.status_code, 403)

    def test_p4_analytics_returns_aggregates_without_citizen_pii(self):
        db.add_complaint({"id":"CH-2026-P4TEST", "title":"P4 analytics fixture",
            "description":"Test water issue", "phone":"DO-NOT-RETURN",
            "address":"Test District, Jharkhand", "district":"Test District", "department":"Water",
            "priority":"High", "status":"Resolved", "created_at":"2026-08-12T10:00:00"})
        db.add_user({"id":"P4-ADMIN", "name":"P4 Admin", "username":"p4_admin",
            "phone":"+919876549999", "password_hash":main.hash_password("A-Long-Test-Password-2026"),
            "role":"govt_admin", "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        token = main.create_token("p4_admin", "govt_admin", "P4-ADMIN")
        response = self.client.get("/api/admin/impact-analytics", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertGreaterEqual(body["total_challenges"], 1)
        self.assertIn("by_district", body)
        self.assertIn("monthly_trend", body)
        self.assertNotIn("phone", body)
        self.assertNotIn("DO-NOT-RETURN", response.text)
        filtered = self.client.get("/api/admin/impact-analytics?date_from=2026-08-01&date_to=2026-08-31&district=Test%20District&department=Water", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(filtered.status_code, 200, filtered.text)
        filtered_body = filtered.json()
        self.assertGreaterEqual(filtered_body["total_challenges"], 1)
        self.assertEqual(filtered_body["filters"]["district"], "Test District")
        self.assertTrue(any(row["label"] == "Test District" for row in filtered_body["by_district"]))
        self.assertIn("All-time", filtered_body["non_complaint_metrics_scope"])
        bad_dates = self.client.get("/api/admin/impact-analytics?date_from=2026-09-01&date_to=2026-08-01", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(bad_dates.status_code, 422)


    def test_logout_all_revokes_all_sessions_for_current_user(self):
        db.add_user({"id":"SESSION-USER", "name":"Session User", "username":"session_user",
            "phone":"+919876540088", "password_hash":main.hash_password("A-Long-Test-Password-2026"),
            "role":"citizen", "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        token_a = main.create_token("session_user", "citizen", "SESSION-USER")
        token_b = main.create_token("session_user", "citizen", "SESSION-USER")
        other_token = main.create_token("other_user", "citizen", "OTHER-USER")
        response = self.client.post("/auth/logout-all", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreaterEqual(response.json()["revoked_sessions"], 2)
        self.assertIsNone(db.get_session(__import__("hashlib").sha256(token_a.encode()).hexdigest()))
        self.assertIsNone(db.get_session(__import__("hashlib").sha256(token_b.encode()).hexdigest()))
        self.assertIsNotNone(db.get_session(__import__("hashlib").sha256(other_token.encode()).hexdigest()))

    def test_logout_revokes_only_presented_session(self):
        db.add_user({"id":"SINGLE-SESSION-USER", "name":"Single Session", "username":"single_session",
            "phone":"+919876540089", "password_hash":main.hash_password("A-Long-Test-Password-2026"),
            "role":"citizen", "organization":"", "department":"", "created_at":"2026-01-01T00:00:00"})
        token_a = main.create_token("single_session", "citizen", "SINGLE-SESSION-USER")
        token_b = main.create_token("single_session", "citizen", "SINGLE-SESSION-USER")
        response = self.client.post("/auth/logout", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.get_session(__import__("hashlib").sha256(token_a.encode()).hexdigest()))
        self.assertIsNotNone(db.get_session(__import__("hashlib").sha256(token_b.encode()).hexdigest()))


    def test_status_transition_enqueues_notification_atomically(self):
        db.add_complaint({"id": "OUTBOX-ATOMIC-1", "title": "Outbox test", "description": "Test",
                          "phone": "+919876549001", "status": "Crowdsourced"})
        result = db.update_complaint_status_atomic("OUTBOX-ATOMIC-1", {"status": "Under Review"},
                                                   actor_user_id="reviewer", actor_role="govt_admin")
        self.assertTrue(result["status_changed"])
        conn = db._connect()
        try:
            rows = conn.execute("SELECT * FROM notification_outbox WHERE dedupe_key LIKE 'complaint-status:OUTBOX-ATOMIC-1:%'").fetchall()
            history = conn.execute("SELECT * FROM complaint_status_history WHERE complaint_id='OUTBOX-ATOMIC-1' AND new_status='Under Review'").fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertEqual(len(history), 1)

    def test_notification_finish_records_simulated_mode(self):
        now = __import__('datetime').datetime.now().isoformat()
        conn = db._connect()
        try:
            conn.execute("INSERT INTO notification_outbox (dedupe_key, recipient, message, status, created_at, updated_at, next_attempt_at) VALUES (?,?,?,?,?,?,?)",
                         ("test-simulated-mode", "+919876549002", "test", "processing", now, now, now))
            notification_id = conn.execute("SELECT id FROM notification_outbox WHERE dedupe_key='test-simulated-mode'").fetchone()["id"]
            conn.commit()
        finally:
            conn.close()
        self.assertTrue(db.finish_notification(notification_id, True, delivery_mode="simulated"))
        conn = db._connect()
        try:
            row = conn.execute("SELECT status, delivery_mode FROM notification_outbox WHERE id=?", (notification_id,)).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["status"], "sent")
        self.assertEqual(row["delivery_mode"], "simulated")



    def test_citizen_cannot_create_case_room_milestone(self):
        db.add_complaint({"id": "MILESTONE-SEC-1", "title": "Milestone security test", "description": "Test",
                          "phone": "+919876549099", "status": "Verified"})
        db.add_user({"id": "MILESTONE-CITIZEN", "name": "Milestone Citizen", "username": "milestone_citizen",
                     "phone": "+919876549098", "password_hash": main.hash_password("A-Long-Test-Password-2026"),
                     "role": "citizen", "organization": "", "department": ""})
        token = main.create_token("milestone_citizen", "citizen", "MILESTONE-CITIZEN")
        response = self.client.post("/api/challenges/MILESTONE-SEC-1/milestones", headers={"Authorization": f"Bearer {token}"}, json={
            "challenge_id": "MILESTONE-SEC-1", "title": "Unauthorized update", "progress_percent": 50, "status": "in_progress"
        })
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(db.get_milestones("MILESTONE-SEC-1"), [])

    def test_government_reviews_milestone_and_controls_pilot_transition(self):
        db.add_complaint({"id": "MILESTONE-REVIEW-1", "title": "Review workflow", "description": "Test",
                          "phone": "+919876549095", "status": "In Progress"})
        db.add_user({"id": "MILESTONE-REVIEW-GOV", "name": "Review Authority", "username": "milestone_review_gov",
                     "phone": "+919876549094", "password_hash": main.hash_password("A-Long-Test-Password-2026"),
                     "role": "govt_admin", "organization": "Test Authority", "department": ""})
        db.add_user({"id": "MILESTONE-REVIEW-CIT", "name": "Review Citizen", "username": "milestone_review_cit",
                     "phone": "+919876549093", "password_hash": main.hash_password("A-Long-Test-Password-2026"),
                     "role": "citizen", "organization": "", "department": ""})
        govt = {"Authorization": f"Bearer {main.create_token('milestone_review_gov', 'govt_admin', 'MILESTONE-REVIEW-GOV')}"}
        citizen = {"Authorization": f"Bearer {main.create_token('milestone_review_cit', 'citizen', 'MILESTONE-REVIEW-CIT')}"}
        created = self.client.post("/api/challenges/MILESTONE-REVIEW-1/milestones", headers=govt, json={
            "challenge_id": "MILESTONE-REVIEW-1", "title": "Field validation", "progress_percent": 100,
            "status": "completed", "proof_url": "https://example.test/evidence"
        })
        self.assertEqual(created.status_code, 200, created.text)
        milestone_id = created.json()["milestone_id"]
        denied = self.client.put(f"/api/challenges/MILESTONE-REVIEW-1/milestones/{milestone_id}/review",
                                 headers=citizen, json={"decision": "approved", "note": "Looks good"})
        self.assertEqual(denied.status_code, 403)
        blocked = self.client.put("/api/challenges/MILESTONE-REVIEW-1/status", headers=govt, json={"status": "Pilot"})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        reviewed = self.client.put(f"/api/challenges/MILESTONE-REVIEW-1/milestones/{milestone_id}/review",
                                   headers=govt, json={"decision": "approved", "note": "Evidence reviewed"})
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["milestone"]["review_decision"], "approved")
        pilot = self.client.put("/api/challenges/MILESTONE-REVIEW-1/status", headers=govt, json={"status": "Pilot"})
        self.assertEqual(pilot.status_code, 200, pilot.text)
        resolved = self.client.put("/api/challenges/MILESTONE-REVIEW-1/status", headers=govt, json={"status": "Resolved"})
        self.assertEqual(resolved.status_code, 200, resolved.text)

    def test_milestone_rejects_non_http_evidence_url(self):
        db.add_complaint({"id": "MILESTONE-URL-1", "title": "Milestone URL test", "description": "Test",
                          "phone": "+919876549097", "status": "Verified"})
        db.add_user({"id": "MILESTONE-GOVT", "name": "Milestone Reviewer", "username": "milestone_reviewer",
                     "phone": "+919876549096", "password_hash": main.hash_password("A-Long-Test-Password-2026"),
                     "role": "govt_admin", "organization": "Test Authority", "department": ""})
        token = main.create_token("milestone_reviewer", "govt_admin", "MILESTONE-GOVT")
        response = self.client.post("/api/challenges/MILESTONE-URL-1/milestones", headers={"Authorization": f"Bearer {token}"}, json={
            "challenge_id": "MILESTONE-URL-1", "title": "Evidence", "progress_percent": 25,
            "status": "in_progress", "proof_url": "javascript:alert(1)"
        })
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(db.get_milestones("MILESTONE-URL-1"), [])



if __name__ == "__main__":
    unittest.main()
