import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import main
from main import app, classify_societal_challenge, send_sms

client = TestClient(app)

class TestExternalServices(unittest.TestCase):

    def test_classify_societal_challenge_heuristics(self):
        # Test water leak problem classification
        result = classify_societal_challenge("Severe pipeline leakage causing water shortage and street flooding", "Broken Pipeline")
        self.assertEqual(result["category"], "Water & Sanitation")
        self.assertIn("SDG 6", result["sdg_tag"])
        self.assertTrue(len(result["ai_tech_stack"]) > 0)
        self.assertTrue(len(result["ai_recommended_depts"]) > 0)

        # Test health problem classification
        result2 = classify_societal_challenge("Local community clinic lacks medical supplies and dengue fever is spreading", "Dengue Outbreak")
        self.assertEqual(result2["category"], "Healthcare & Community Health")
        self.assertIn("SDG 3", result2["sdg_tag"])
        self.assertEqual(result2["priority"], "Medium")

    def test_send_sms_simulation_mode(self):
        with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "FAST2SMS_API_KEY": ""}):
            res = send_sms("9876543210", "Challenge CH-2026-0001 verified")
            self.assertTrue(res.get("success"))
            self.assertTrue(res.get("simulated"))

    @patch("main.requests.post")
    def test_send_sms_fast2sms(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"return": True, "request_id": "fast-123", "message": ["SMS sent successfully"]}
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"FAST2SMS_API_KEY": "dummy_fast_key", "TWILIO_ACCOUNT_SID": ""}):
            res = send_sms("9876543210", "Fast2SMS Alert")
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("provider"), "fast2sms")

    @patch("main.requests.post")
    def test_send_sms_twilio(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SM12345", "status": "queued"}
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {
            "TWILIO_ACCOUNT_SID": "AC12345",
            "TWILIO_AUTH_TOKEN": "auth_token_xyz",
            "TWILIO_FROM_PHONE": "+1234567890"
        }):
            res = send_sms("9876543210", "Twilio Alert")
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("provider"), "twilio")

    def test_ai_chat_endpoint_valid(self):
        resp = client.post("/api/ai/chat", json={"message": "Namaste, what can I do on NagrikSnap?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("Jan Sevak", data.get("reply", ""))
        self.assertIn("engine", data)

    def test_ai_chat_endpoint_empty_message(self):
        resp = client.post("/api/ai/chat", json={"message": "   "})
        self.assertEqual(resp.status_code, 422)

if __name__ == "__main__":
    unittest.main()
