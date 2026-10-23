import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.models.http_client import JsonModel
from sdk.protocol import CoreError, canonical


class FakeProcess:
    returncode = 0
    def __init__(self, payload): self.payload = payload; self.killed = False
    def communicate(self, *args, **kwargs): return canonical(self.payload).encode(), b""
    def poll(self): return self.returncode
    def kill(self): self.killed = True; self.returncode = -1


class ModelTransportCase(unittest.TestCase):
    def config(self):
        return {"id": "test", "model": "test-model", "endpoint": "https://example.test/v1/chat/completions",
                "key_env": "JARVIS_TRANSPORT_TEST_KEY", "max_output_tokens": 512, "timeout_seconds": 5}

    def test_missing_key_never_starts_http_child(self):
        with patch.dict(os.environ, {}, clear=True), patch("subprocess.Popen") as start:
            self.assertEqual(JsonModel(self.config()).generate("JSON")['status'], "REJECTED")
            start.assert_not_called()

    def test_endpoint_cannot_select_plaintext_or_credentials(self):
        for endpoint in ["http://example.test/v1/chat/completions", "https://key@example.test/v1/chat/completions", "https://example.test/v1/chat/completions?token=secret"]:
            config = self.config(); config["endpoint"] = endpoint
            with self.assertRaises(CoreError): JsonModel(config)

    def test_usage_completion_bounds_and_secret_environment(self):
        payload = {"status": "RECEIVED", "body": {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}], "usage": {"total_tokens": 12}}}
        with patch.dict(os.environ, {"JARVIS_TRANSPORT_TEST_KEY": "test-secret", "UNRELATED_SECRET": "never-forward"}), patch("subprocess.Popen", return_value=FakeProcess(payload)) as start:
            result = JsonModel(self.config()).generate("Return JSON")
            self.assertEqual(result["usage"], {"total_tokens": 12})
            self.assertEqual(result["value"], {"ok": True})
            env = start.call_args.kwargs["env"]
            self.assertNotIn("UNRELATED_SECRET", env)
            self.assertNotIn("test-secret", str(start.call_args.args))
        payload["body"]["choices"][0]["finish_reason"] = "length"
        with patch.dict(os.environ, {"JARVIS_TRANSPORT_TEST_KEY": "test-secret"}), patch("subprocess.Popen", return_value=FakeProcess(payload)):
            self.assertEqual(JsonModel(self.config()).generate("JSON")["status"], "INVALID")

    def test_cancel_terminates_transport(self):
        process = FakeProcess({}); process.returncode = None
        count = 0
        def checkpoint():
            nonlocal count
            count += 1
            if count > 1: raise CoreError("stopped", "test")
        with patch.dict(os.environ, {"JARVIS_TRANSPORT_TEST_KEY": "test-secret"}), patch("subprocess.Popen", return_value=process):
            with self.assertRaises(CoreError): JsonModel(self.config()).generate("JSON", checkpoint)
        self.assertTrue(process.killed)


if __name__ == "__main__": unittest.main()
