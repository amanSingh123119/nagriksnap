"""Evidence storage adapter tests; run with unittest discovery."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import storage


class EvidenceStorageTests(unittest.TestCase):
    def test_local_round_trip_uses_private_filename_and_content_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(storage, "STORAGE_MODE", "local"), patch.object(storage, "LOCAL_UPLOAD_DIR", Path(temp_dir)):
                key = storage.save_evidence("CH-2026-ABCDEF_aabb.jpg", b"image-bytes", "image/jpeg")
                self.assertEqual(key, "CH-2026-ABCDEF_aabb.jpg")
                self.assertEqual(storage.read_evidence(key), (b"image-bytes", "image/jpeg"))

    def test_local_storage_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(storage, "STORAGE_MODE", "local"), patch.object(storage, "LOCAL_UPLOAD_DIR", Path(temp_dir)):
                with self.assertRaises(ValueError):
                    storage.save_evidence("../secret.jpg", b"x", "image/jpeg")
                self.assertIsNone(storage.read_evidence("../secret.jpg"))

    def test_s3_requires_bucket_configuration(self):
        with patch.object(storage, "STORAGE_MODE", "s3"), patch.object(storage, "S3_BUCKET", ""):
            with self.assertRaisesRegex(RuntimeError, "S3_BUCKET is required"):
                storage.validate_configuration()

    def test_unknown_storage_mode_fails_closed(self):
        with patch.object(storage, "STORAGE_MODE", "unknown"):
            with self.assertRaisesRegex(RuntimeError, "EVIDENCE_STORAGE_MODE"):
                storage.validate_configuration()

    def test_s3_presigned_url_generation(self):
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/CH-2026-TEST.jpg?signed=true"
        with patch.object(storage, "STORAGE_MODE", "s3"), patch.object(storage, "S3_BUCKET", "prod-evidence-bucket"), patch.object(storage, "_s3_client", return_value=mock_client):
            url = storage.generate_presigned_download_url("CH-2026-TEST.jpg")
            self.assertEqual(url, "https://s3.example.com/CH-2026-TEST.jpg?signed=true")
            mock_client.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={"Bucket": "prod-evidence-bucket", "Key": "CH-2026-TEST.jpg"},
                ExpiresIn=3600
            )

    def test_verify_storage_health(self):
        with patch.object(storage, "STORAGE_MODE", "s3"), patch.object(storage, "S3_BUCKET", "prod-evidence-bucket"), patch.object(storage, "S3_REGION", "ap-south-1"):
            health = storage.verify_storage_health()
            self.assertEqual(health["mode"], "s3")
            self.assertEqual(health["bucket"], "prod-evidence-bucket")
            self.assertEqual(health["region"], "ap-south-1")


if __name__ == "__main__":
    unittest.main()
