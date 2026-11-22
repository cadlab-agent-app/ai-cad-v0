"""Vision tests. Everything is mocked: no network, no real key. Run: python -m unittest discover -s tests -v"""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

_OUTPUT = tempfile.TemporaryDirectory()
os.environ["CAD_OUTPUT_DIR"] = _OUTPUT.name
from fastapi.testclient import TestClient
from PIL import Image
from app import main, vision
from app.templates import TEMPLATES

KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "VISION_PROVIDER", "GEMINI_MODEL", "GEMINI_MODEL_FALLBACKS")


def env(**kw):
    base = {k: v for k, v in os.environ.items() if k not in KEYS}
    base.update(kw)
    return patch.dict(os.environ, base, clear=True)


def png(size=(64, 48), fmt="PNG", color="white"):
    buf = io.BytesIO(); Image.new("RGB", size, color).save(buf, fmt); return buf.getvalue()


def defaults(name):
    return {k: f.default for k, f in TEMPLATES[name]["fields"].items()}


def full(name, **over):
    return {"part_type": name, "dimensions": {**{k: float(v) for k, v in defaults(name).items()}, **over},
            "confidence": "high", "notes": "ok"}


class VisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._vision_calls.clear(); main._vision_global.clear()

    def post(self, data, name="s.png", mime="image/png"):
        return self.client.post("/api/interpret", files={"image": (name, data, mime)})

    # --- disabled path -------------------------------------------------
    def test_disabled_without_key(self):
        with env():
            self.assertFalse(vision.is_configured())
            self.assertFalse(self.client.get("/api/health").json()["vision_configured"])
            r = self.post(png())
            self.assertEqual(r.status_code, 503)
            self.assertIn("disabled", r.json()["detail"])
            with self.assertRaises(vision.VisionNotConfigured):
                vision.extract_part(png(), "image/png")
            # manual CAD still fine
            r = self.client.post("/api/generate", json={"part_type": "plate", "dimensions": defaults("plate")})
            self.assertEqual(r.status_code, 200)

    def test_provider_selection(self):
        with env(): self.assertIsNone(vision.provider_name())
        with env(GEMINI_API_KEY="g"): self.assertEqual(vision.provider_name(), "gemini")
        with env(OPENAI_API_KEY="o"): self.assertEqual(vision.provider_name(), "openai")
        with env(GEMINI_API_KEY="g", OPENAI_API_KEY="o"): self.assertEqual(vision.provider_name(), "gemini")
        with env(GEMINI_API_KEY="g", OPENAI_API_KEY="o", VISION_PROVIDER="openai"): self.assertEqual(vision.provider_name(), "openai")
        with env(GEMINI_API_KEY="g", VISION_PROVIDER="openai"): self.assertIsNone(vision.provider_name())
        with env(GEMINI_API_KEY="   "): self.assertIsNone(vision.provider_name())

    # --- happy path per template --------------------------------------
    def test_happy_path_each_template(self):
        for name in TEMPLATES:
            with self.subTest(template=name), env(GEMINI_API_KEY="k"), \
                    patch("app.vision._call_vision_provider", return_value=full(name)):
                r = self.post(png())
                self.assertEqual(r.status_code, 200, r.text)
                body = r.json()
                self.assertEqual(body["part_type"], name)
                self.assertEqual(body["missing"], [])
                self.assertTrue(body["requires_confirmation"])
                self.assertEqual(body["dimensions"], {k: float(v) for k, v in defaults(name).items()})
                # confirmed values generate through the normal checked path
                g = self.client.post("/api/generate", json={"part_type": name, "dimensions": body["dimensions"]})
                self.assertEqual(g.status_code, 200, g.text)

    def test_missing_dimensions_are_flagged(self):
        proposal = {"part_type": "bushing", "dimensions": {"outer_diameter": 40, "inner_diameter": None, "height": "tall"}}
        with env(GEMINI_API_KEY="k"), patch("app.vision._call_vision_provider", return_value=proposal):
            body = self.post(png()).json()
        self.assertEqual(body["dimensions"]["outer_diameter"], 40.0)
        self.assertEqual(sorted(body["missing"]), ["height", "inner_diameter"])

    def test_no_readable_dimensions_rejected(self):
        for dims in ({}, {"height": None}, {"height": 99999}, "x", None):
            with self.subTest(dims=dims), env(GEMINI_API_KEY="k"), patch(
                    "app.vision._call_vision_provider", return_value={"part_type": "bushing", "dimensions": dims}):
                self.assertEqual(self.post(png()).status_code, 422)

    def test_unsupported_part_and_model_error(self):
        with env(GEMINI_API_KEY="k"):
            with patch("app.vision._call_vision_provider", return_value={"part_type": "gear", "dimensions": {"a": 1}}):
                self.assertEqual(self.post(png()).status_code, 422)
            with patch("app.vision._call_vision_provider", return_value={"error": "This is a cat photo"}):
                r = self.post(png()); self.assertEqual(r.status_code, 422); self.assertIn("cat", r.json()["detail"])
            with patch("app.vision._call_vision_provider", return_value=["not", "dict"]):
                self.assertEqual(self.post(png()).status_code, 422)

    def test_injected_code_or_extra_keys_are_ignored(self):
        p = full("plate"); p["code"] = "__import__('os').system('x')"; p["dimensions"]["evil"] = "import os"
        with env(GEMINI_API_KEY="k"), patch("app.vision._call_vision_provider", return_value=p):
            body = self.post(png()).json()
        self.assertNotIn("code", body); self.assertNotIn("evil", body["dimensions"])

    # --- bad input -----------------------------------------------------
    def test_garbage_image(self):
        garbage = b"\x89PNG\r\n\x1a\n" + os.urandom(200)  # valid header, undecodable body
        with env(GEMINI_API_KEY="k"), patch("app.vision._call_vision_provider") as call:
            r = self.post(garbage)
            self.assertEqual(r.status_code, 422)
            call.assert_not_called()  # never paid for a garbage upload

    def test_wrong_types(self):
        with env(GEMINI_API_KEY="k"), patch("app.vision._call_vision_provider") as call:
            self.assertEqual(self.post(b"<svg/>", "a.svg", "image/svg+xml").status_code, 415)
            self.assertEqual(self.post(b"%PDF-1.4 hi", "a.pdf", "application/pdf").status_code, 415)
            self.assertEqual(self.post(b"", "e.png").status_code, 422)
            call.assert_not_called()

    def test_oversized(self):
        big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10)
        with env(GEMINI_API_KEY="k"), patch("app.vision._call_vision_provider") as call:
            self.assertEqual(self.post(big).status_code, 413)
            call.assert_not_called()

    def test_jpeg_and_webp_accepted(self):
        for fmt, mime in (("JPEG", "image/jpeg"), ("WEBP", "image/webp")):
            with self.subTest(fmt=fmt), env(GEMINI_API_KEY="k"), patch(
                    "app.vision._call_vision_provider", return_value=full("plate")):
                self.assertEqual(self.post(png(fmt=fmt), "s", mime).status_code, 200)

    # --- provider errors -----------------------------------------------
    def test_provider_error_is_502(self):
        with env(GEMINI_API_KEY="k"), patch("app.vision._call_vision_provider",
                                            side_effect=vision.VisionProviderError("Vision request failed: x.")):
            self.assertEqual(self.post(png()).status_code, 502)

    def test_rate_limit(self):
        with env(GEMINI_API_KEY="k"), patch.object(main, "VISION_PER_IP_HOUR", 2), patch(
                "app.vision._call_vision_provider", return_value=full("plate")):
            codes = [self.post(png()).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    # --- adapters (HTTP mocked) -----------------------------------------
    @staticmethod
    def http_ok(payload):
        resp = MagicMock(); resp.read.return_value = json.dumps(payload).encode()
        resp.__enter__.return_value = resp; return resp

    @staticmethod
    def http_err(code):
        return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(b'{"secret":"sk-leak"}'))

    def gemini_payload(self, obj):
        return {"candidates": [{"content": {"parts": [{"text": "```json\n" + json.dumps(obj) + "\n```"}]}}]}

    def test_gemini_adapter_request_and_parse(self):
        seen = {}
        def fake(req, timeout):
            seen["url"] = req.full_url; seen["headers"] = dict(req.header_items()); seen["body"] = json.loads(req.data)
            return self.http_ok(self.gemini_payload(full("bracket")))
        with env(GEMINI_API_KEY="KEY123"), patch("urllib.request.urlopen", side_effect=fake):
            out = vision.extract_part(png(), "image/png")
        self.assertEqual(out["part_type"], "bracket")
        self.assertIn("generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent", seen["url"])
        self.assertNotIn("KEY123", seen["url"])
        self.assertEqual(seen["headers"]["X-goog-api-key"], "KEY123")
        part = seen["body"]["contents"][0]["parts"][1]["inline_data"]
        self.assertEqual(part["mime_type"], "image/jpeg")  # re-encoded and downscaled
        self.assertEqual(seen["body"]["generationConfig"]["responseMimeType"], "application/json")

    def test_gemini_model_fallback_chain(self):
        urls = []
        def fake(req, timeout):
            urls.append(req.full_url)
            if len(urls) == 1: raise self.http_err(429)
            if len(urls) == 2: raise self.http_err(404)
            return self.http_ok(self.gemini_payload(full("plate")))
        with env(GEMINI_API_KEY="k"), patch("urllib.request.urlopen", side_effect=fake):
            out = vision.extract_part(png(), "image/png")
        self.assertEqual(out["part_type"], "plate")
        self.assertEqual(len(urls), 3)
        self.assertIn("gemini-3.5-flash-lite", urls[2])

    def test_gemini_errors(self):
        with env(GEMINI_API_KEY="k"):
            with patch("urllib.request.urlopen", side_effect=self.http_err(401)):
                with self.assertRaises(vision.VisionProviderError) as cm: vision.extract_part(png(), "image/png")
                self.assertIn("key was rejected", str(cm.exception)); self.assertNotIn("sk-leak", str(cm.exception))
            with patch("urllib.request.urlopen", side_effect=self.http_err(429)):
                with self.assertRaises(vision.VisionProviderError) as cm: vision.extract_part(png(), "image/png")
                self.assertIn("quota", str(cm.exception))
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
                with self.assertRaises(vision.VisionProviderError): vision.extract_part(png(), "image/png")
            with patch("urllib.request.urlopen", side_effect=TimeoutError()):
                with self.assertRaises(vision.VisionProviderError): vision.extract_part(png(), "image/png")
            with patch("urllib.request.urlopen", return_value=self.http_ok({"candidates": []})):
                with self.assertRaises(vision.VisionProviderError): vision.extract_part(png(), "image/png")
            with patch("urllib.request.urlopen", return_value=self.http_ok({"candidates": [{"content": {"parts": [{"text": "not json"}]}}]})):
                with self.assertRaises(vision.VisionProviderError): vision.extract_part(png(), "image/png")

    def test_openai_adapter(self):
        seen = {}
        def fake(req, timeout):
            seen["url"] = req.full_url; seen["auth"] = req.get_header("Authorization")
            return self.http_ok({"choices": [{"message": {"content": json.dumps(full("enclosure"))}}]})
        with env(OPENAI_API_KEY="sk-test"), patch("urllib.request.urlopen", side_effect=fake):
            out = vision.extract_part(png(), "image/png")
        self.assertEqual(out["part_type"], "enclosure")
        self.assertEqual(seen["url"], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer sk-test")
        with env(OPENAI_API_KEY="sk-test"), patch("urllib.request.urlopen", side_effect=self.http_err(401)):
            with self.assertRaises(vision.VisionProviderError): vision.extract_part(png(), "image/png")

    def test_prepare_image_downscales_and_handles_alpha(self):
        buf = io.BytesIO(); Image.new("RGBA", (4000, 3000), (0, 0, 0, 0)).save(buf, "PNG")
        out, mime = vision.prepare_image(buf.getvalue())
        self.assertEqual(mime, "image/jpeg")
        self.assertLessEqual(max(Image.open(io.BytesIO(out)).size), vision.SEND_MAX_EDGE)


if __name__ == "__main__":
    unittest.main()
