"""Focused checks for scripts/gen-image multi-image edit uploads.

The Meta API rejects SDK-style ``image[]`` multipart parts with a 400 and
requires ``image[0]``, ``image[1]``, ... numbered consecutively from 0, so
multi-image edits bypass the SDK (see edit_images_indexed).

Run with: python -m unittest scripts.test_gen_image -v
"""
import base64
import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _load_gen_image():
    import importlib.machinery

    path = Path(__file__).resolve().parent / "gen-image"
    loader = importlib.machinery.SourceFileLoader("gen_image_under_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


gen_image = _load_gen_image()


class StubServerTest(unittest.TestCase):
    """Local stub asserting wire format; no API key or network needed."""

    def setUp(self):
        self.received = []
        received = self.received
        self.mode = {"status": 200, "payload": {"data": []}}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - http.server convention
                length = int(self.headers.get("Content-Length") or 0)
                received.append((self.headers.get("Content-Type"),
                                 self.rfile.read(length)))
                data = json.dumps(self.server.mode["payload"]).encode()  # type: ignore[attr-defined]
                self.send_response(self.server.mode["status"])  # type: ignore[attr-defined]
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.mode = self.mode  # type: ignore[attr-defined]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _ref(self, name, content=b"fakepng-bytes"):
        path = Path(self.tmp.name) / name
        path.write_bytes(content)
        return str(path)

    @staticmethod
    def _part_names(body):
        return re.findall(rb'name="([^"]+)"', body)

    def test_multipart_names_are_indexed_in_order(self):
        body, ctype = gen_image._multipart_encode(
            {"model": "m", "prompt": "p"},
            [("image[0]", "a.png", b"AAA", "image/png"),
             ("image[1]", "b.png", b"BBB", "image/png")])
        self.assertIn("multipart/form-data; boundary=", ctype)
        names = self._part_names(body)
        self.assertEqual(names[:2], [b"model", b"prompt"])
        self.assertEqual([n for n in names if n.startswith(b"image")],
                         [b"image[0]", b"image[1]"])
        self.assertNotIn(b"image[]", body)
        self.assertIn(b"AAA", body)
        self.assertIn(b"BBB", body)
        self.assertTrue(body.rstrip().endswith(b"--"))

    def test_edit_posts_indexed_parts(self):
        self.mode["payload"] = {"data": [{"b64_json": PNG_1X1_B64}],
                                "usage": {"input_tokens": 3, "output_tokens": 5}}
        refs = [self._ref("a.png", b"AAA"), self._ref("b.png", b"BBB")]
        resp = gen_image.edit_images_indexed(
            self.base_url, "dummy", model="muse-image-1.0", prompt="p",
            ref_paths=refs, size="1024x1024", num=1,
            output_format="png", timeout=30)
        self.assertEqual(len(self.received), 1)
        ctype, body = self.received[0]
        self.assertIn("multipart/form-data", ctype)
        self.assertEqual([n for n in self._part_names(body)
                          if n.startswith(b"image")],
                         [b"image[0]", b"image[1]"])
        self.assertNotIn(b"image[]", body)
        self.assertEqual(resp.data[0].b64_json, PNG_1X1_B64)
        self.assertEqual(resp.usage.input_tokens, 3)
        self.assertEqual(resp.usage.output_tokens, 5)

    def test_edit_http_error_exits_1(self):
        self.mode.update(status=400, payload={"error": {"message": "bad image key"}})
        refs = [self._ref("a.png"), self._ref("b.png")]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                gen_image.edit_images_indexed(
                    self.base_url, "dummy", model="m", prompt="p",
                    ref_paths=refs, size="1024x1024", num=1,
                    output_format="png", timeout=30)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("400", err.getvalue())

    def test_cli_multi_ref_run_writes_output(self):
        self.mode["payload"] = {"data": [{"b64_json": PNG_1X1_B64}]}
        refs = [self._ref("a.png", b"AAA"), self._ref("b.png", b"BBB")]
        out = str(Path(self.tmp.name) / "out.png")
        code = gen_image.main(["--prompt", "p", "-i", refs[0], "-i", refs[1],
                               "-o", out, "--no-record", "--no-resize",
                               "--api-key", "dummy", "--base-url", self.base_url])
        self.assertEqual(code, 0)
        self.assertEqual(Path(out).read_bytes(), base64.b64decode(PNG_1X1_B64))
        _, body = self.received[0]
        self.assertNotIn(b"image[]", body)


if __name__ == "__main__":
    unittest.main()
