"""Proves the YouTube uploader's permanent safety rule actually holds
(private by default, PUBLIC_UPLOAD refused without double opt-in), missing
credentials return UPLOAD_NOT_CONFIGURED without crashing, and the real
resumable-upload request construction is correct against a mocked
transport (network itself is never touched in tests)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import youtube_uploader as uploader

STRONG_METADATA = {
    "title": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?",
    "description": "Açıklama metni.",
    "tags": ["gizem", "tarih"],
    "category": "Education",
    "language": "tr",
    "visibility": "private",
}


class UploaderSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name, attr in [
            ("ROOT", self.projects), ("SCRIPT_DIR", self.projects / "script-agent"),
            ("OUTPUT_DIR", self.projects / "youtube-upload"),
        ]:
            p = mock.patch.object(uploader, name, attr)
            p.start()
            self.addCleanup(p.stop)

    def _write(self, relpath: str, data) -> None:
        path = self.projects / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_default_mode_is_dry_run(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("YOUTUBE_UPLOAD_MODE", None)
            self.assertEqual(uploader.get_mode(), "DRY_RUN")

    def test_dry_run_never_requires_credentials_or_video_ceo_approval(self):
        # No script-agent/video-ceo/video-engine data at all.
        with mock.patch.dict("os.environ", {"YOUTUBE_UPLOAD_MODE": "DRY_RUN"}, clear=False):
            uploader.main()
        result = json.loads((self.projects / "youtube-upload" / "upload_result.json").read_text(encoding="utf-8"))
        self.assertIn(result["status"], {"DRY_RUN_OK", "DRY_RUN_VALIDATION_FAILED"})
        self.assertEqual(result["privacy_status"], "private")

    def test_public_upload_blocked_without_explicit_allow_flag(self):
        with mock.patch.dict("os.environ", {"YOUTUBE_UPLOAD_MODE": "PUBLIC_UPLOAD"}, clear=False):
            import os
            os.environ.pop("YOUTUBE_ALLOW_PUBLIC", None)
            uploader.main()
        result = json.loads((self.projects / "youtube-upload" / "upload_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "PUBLIC_UPLOAD_BLOCKED")
        self.assertEqual(result["privacy_status"], "private")

    def test_public_upload_still_requires_video_ceo_cek_even_with_allow_flag(self):
        self._write("video-ceo/analysis.json", {"decision": "DUR"})
        with mock.patch.dict("os.environ", {"YOUTUBE_UPLOAD_MODE": "PUBLIC_UPLOAD", "YOUTUBE_ALLOW_PUBLIC": "true"}, clear=False):
            uploader.main()
        result = json.loads((self.projects / "youtube-upload" / "upload_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "NOT_READY")

    def test_private_upload_not_ready_when_video_ceo_did_not_approve(self):
        self._write("video-ceo/analysis.json", {"decision": "DUR"})
        with mock.patch.dict("os.environ", {"YOUTUBE_UPLOAD_MODE": "PRIVATE_UPLOAD"}, clear=False):
            uploader.main()
        result = json.loads((self.projects / "youtube-upload" / "upload_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "NOT_READY")

    def test_missing_credentials_returns_upload_not_configured_never_crashes(self):
        self._write("video-ceo/analysis.json", {"decision": "ÇEK"})
        self._write("script-agent/youtube_upload.json", STRONG_METADATA)
        video_path = self.projects / "video-engine" / "final_video.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake video bytes")
        thumb_path = self.projects / "frame.png"
        thumb_path.write_bytes(b"fake png bytes")
        self._write("video-engine/render_manifest.json", {
            "final_video": str(video_path),
            "scenes": [{"role": "hook", "image_source": str(thumb_path)}],
        })
        with mock.patch.dict("os.environ", {"YOUTUBE_UPLOAD_MODE": "PRIVATE_UPLOAD"}, clear=False):
            import os
            for key in ["YOUTUBE_OAUTH_ACCESS_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]:
                os.environ.pop(key, None)
            uploader.main()
        result = json.loads((self.projects / "youtube-upload" / "upload_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "UPLOAD_NOT_CONFIGURED")
        self.assertEqual(result["privacy_status"], "private")

    def test_prepare_upload_forces_private_even_if_metadata_says_otherwise(self):
        self._write("video-ceo/analysis.json", {"decision": "ÇEK"})
        metadata = dict(STRONG_METADATA)
        metadata["visibility"] = "public"  # must be ignored — privacy is never trusted from metadata
        self._write("script-agent/youtube_upload.json", metadata)
        video_path = self.projects / "video-engine" / "final_video.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake video bytes")
        thumb_path = self.projects / "frame.png"
        thumb_path.write_bytes(b"fake png bytes")
        self._write("video-engine/render_manifest.json", {
            "final_video": str(video_path),
            "scenes": [{"role": "hook", "image_source": str(thumb_path)}],
        })
        with mock.patch.dict("os.environ", {"YOUTUBE_UPLOAD_MODE": "PREPARE_UPLOAD"}, clear=False):
            uploader.main()
        result = json.loads((self.projects / "youtube-upload" / "upload_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "PREPARED")
        self.assertEqual(result["privacy_status"], "private")
        self.assertEqual(result["request_body"]["status"]["privacyStatus"], "private")

    def test_validation_catches_missing_video_and_thumbnail(self):
        self._write("video-ceo/analysis.json", {"decision": "ÇEK"})
        self._write("script-agent/youtube_upload.json", {"title": "", "description": "", "tags": []})
        with mock.patch.dict("os.environ", {"YOUTUBE_UPLOAD_MODE": "PREPARE_UPLOAD"}, clear=False):
            uploader.main()
        result = json.loads((self.projects / "youtube-upload" / "upload_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "VALIDATION_FAILED")
        self.assertTrue(any("Başlık" in e for e in result["validation_errors"]))
        self.assertTrue(any("video" in e.lower() for e in result["validation_errors"]))


class RequestConstructionTests(unittest.TestCase):
    """The real YouTube Data API v3 resumable-upload protocol — only the
    network transport (urlopen) is mocked, everything else is the real
    request-building code."""

    def test_build_request_body_matches_youtube_api_contract(self):
        body = uploader.build_request_body(STRONG_METADATA, "private")
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertEqual(body["snippet"]["categoryId"], "27")
        self.assertEqual(body["snippet"]["title"], STRONG_METADATA["title"])
        self.assertFalse(body["status"]["selfDeclaredMadeForKids"])

    def test_initiate_resumable_session_sends_correct_request(self):
        tmp = Path(tempfile.mkdtemp())
        video = tmp / "v.mp4"
        video.write_bytes(b"x" * 100)
        captured = {}

        class FakeResponse:
            headers = {"Location": "https://upload.example/session123"}
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(request, timeout=30):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.headers)
            return FakeResponse()

        with mock.patch("youtube_uploader.urlopen", fake_urlopen):
            result = uploader.initiate_resumable_session("token123", {"snippet": {}}, str(video))

        self.assertEqual(result, "https://upload.example/session123")
        self.assertIn("uploadType=resumable", captured["url"])
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer token123")
        self.assertEqual(captured["headers"]["X-upload-content-length"], "100")

    def test_initiate_resumable_session_returns_none_on_http_error_not_raise(self):
        from urllib.error import HTTPError
        def fake_urlopen(request, timeout=30):
            raise HTTPError("url", 401, "Unauthorized", {}, None)
        tmp = Path(tempfile.mkdtemp())
        video = tmp / "v.mp4"
        video.write_bytes(b"x")
        with mock.patch("youtube_uploader.urlopen", fake_urlopen):
            result = uploader.initiate_resumable_session("bad-token", {}, str(video))
        self.assertIsNone(result)

    def test_refresh_access_token_prefers_direct_token(self):
        with mock.patch.dict("os.environ", {"YOUTUBE_OAUTH_ACCESS_TOKEN": "direct-token"}, clear=False):
            self.assertEqual(uploader.refresh_access_token(), "direct-token")

    def test_refresh_access_token_exchanges_refresh_token_correctly(self):
        captured = {}

        class FakeResponse:
            def read(self):
                return json.dumps({"access_token": "refreshed-abc"}).encode("utf-8")
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(request, timeout=30):
            captured["url"] = request.full_url
            captured["body"] = request.data.decode("utf-8")
            return FakeResponse()

        env = {
            "YOUTUBE_OAUTH_ACCESS_TOKEN": "",
            "YOUTUBE_CLIENT_ID": "cid", "YOUTUBE_CLIENT_SECRET": "secret",
            "YOUTUBE_REFRESH_TOKEN": "rtoken",
        }
        with mock.patch.dict("os.environ", env, clear=False), \
             mock.patch("youtube_uploader.urlopen", fake_urlopen):
            token = uploader.refresh_access_token()

        self.assertEqual(token, "refreshed-abc")
        self.assertEqual(captured["url"], uploader.TOKEN_URL)
        self.assertIn("grant_type=refresh_token", captured["body"])
        self.assertIn("client_id=cid", captured["body"])


if __name__ == "__main__":
    unittest.main()
