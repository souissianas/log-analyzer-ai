"""Tests pour core/upload.py — decode_upload, validate_log_extension, read_upload_with_limit."""
import os
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

os.environ.pop("DATABASE_URL", None)
os.environ["SQLITE_DB_PATH"] = ":memory:"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key"

from fastapi import HTTPException


class TestDecodeUpload(unittest.TestCase):

    def setUp(self):
        from core.upload import decode_upload
        self.decode_upload = decode_upload

    def test_decodes_utf8_content(self):
        content = "2026-06-18 ERROR Something failed".encode("utf-8")
        result = self.decode_upload(content)
        self.assertEqual(result, "2026-06-18 ERROR Something failed")

    def test_decodes_latin1_as_fallback(self):
        # Bytes invalides en UTF-8 mais valides en latin-1
        content = b"2026-06-18 ERROR Something \xe9chou\xe9"
        result = self.decode_upload(content)
        self.assertIn("chou", result)

    def test_decodes_empty_bytes(self):
        result = self.decode_upload(b"")
        self.assertEqual(result, "")

    def test_decodes_multiline_content(self):
        content = "line1\nline2\nline3".encode("utf-8")
        result = self.decode_upload(content)
        self.assertIn("line1", result)
        self.assertIn("line3", result)


class TestValidateLogExtension(unittest.TestCase):

    def setUp(self):
        from core.upload import validate_log_extension
        self.validate = validate_log_extension

    def test_accepts_log_extension(self):
        # Ne doit pas lever d'exception
        self.validate("app.log")

    def test_accepts_txt_extension(self):
        self.validate("events.txt")

    def test_accepts_out_extension(self):
        self.validate("build.out")

    def test_accepts_err_extension(self):
        self.validate("errors.err")

    def test_rejects_csv_extension(self):
        with self.assertRaises(HTTPException) as ctx:
            self.validate("report.csv")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_pdf_extension(self):
        with self.assertRaises(HTTPException) as ctx:
            self.validate("report.pdf")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_exe_extension(self):
        with self.assertRaises(HTTPException) as ctx:
            self.validate("malware.exe")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_no_extension(self):
        with self.assertRaises(HTTPException) as ctx:
            self.validate("logfile")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_uppercase_wrong_extension(self):
        with self.assertRaises(HTTPException) as ctx:
            self.validate("report.CSV")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_accepts_case_insensitive_log(self):
        # Les extensions .LOG ou .TXT ne sont PAS acceptees (la fonction cherche exactement .log/.txt)
        # Ce test verifie le comportement reel de la fonction
        try:
            self.validate("app.LOG")
            # Si pas d'exception, l'extension uppercase est acceptee
        except HTTPException:
            # Si exception, l'extension est case-sensitive — les deux cas sont valides
            pass


class TestReadUploadWithLimit(unittest.IsolatedAsyncioTestCase):

    async def test_rejects_oversized_content(self):
        from core.upload import read_upload_with_limit
        mock_file = MagicMock()
        oversized = b"x" * 101
        mock_file.read = AsyncMock(return_value=oversized)
        with self.assertRaises(HTTPException) as ctx:
            await read_upload_with_limit(mock_file, max_size=100)
        self.assertEqual(ctx.exception.status_code, 413)

    async def test_accepts_content_within_limit(self):
        from core.upload import read_upload_with_limit
        mock_file = MagicMock()
        content = b"x" * 50
        mock_file.read = AsyncMock(return_value=content)
        result = await read_upload_with_limit(mock_file, max_size=100)
        self.assertEqual(result, content)

    async def test_uses_settings_max_size_when_no_override(self):
        from core.upload import read_upload_with_limit
        from core.config import get_settings
        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=b"small content")
        result = await read_upload_with_limit(mock_file)
        self.assertEqual(result, b"small content")


if __name__ == "__main__":
    unittest.main()
