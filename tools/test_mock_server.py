import http.client
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mock_server  # noqa: E402

KEY = "test-device-key"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


class MockServerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = self._tmp.name
        self.server = mock_server.make_server(0, KEY, self.store, quiet=True)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, args=(0.05,), daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self._tmp.cleanup()

    def request(self, path, body=b"", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", path, body=body, headers=headers or {})
            resp = conn.getresponse()
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
        finally:
            conn.close()

    def photo(self, visit="ps-01-20261103T101500Z-0042", n="1", body=JPEG,
              key=KEY, ctype="image/jpeg"):
        headers = {
            "Content-Type": ctype,
            "X-Station-Id": "ps-01",
            "X-Visit-Id": visit,
            "X-Photo-N": n,
            "X-Captured-At": "",
        }
        if key is not None:
            headers["Authorization"] = "Bearer " + key
        return self.request("/api/photostation/photo", body, headers)

    def post_json(self, path, obj, key=KEY):
        headers = {"Content-Type": "application/json"}
        if key is not None:
            headers["Authorization"] = "Bearer " + key
        return self.request(path, json.dumps(obj).encode(), headers)

    def test_photo_created_then_duplicate_is_200(self):
        status, body = self.photo()
        self.assertEqual(status, 201)
        self.assertEqual(body, {"ok": True, "visit_id": "ps-01-20261103T101500Z-0042", "n": 1})
        status, body = self.photo(body=JPEG + b"different")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        visit_dir = os.path.join(self.store, "ps-01-20261103T101500Z-0042")
        self.assertEqual(os.listdir(visit_dir), ["1.jpg"])
        with open(os.path.join(visit_dir, "1.jpg"), "rb") as f:
            self.assertEqual(f.read(), JPEG)  # first upload is kept

    def test_bad_key_401(self):
        status, body = self.photo(key="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(body["ok"], False)
        status, _ = self.photo(key=None)
        self.assertEqual(status, 401)

    def test_not_jpeg_422(self):
        status, body = self.photo(body=b"\x89PNG\r\n" + b"\x00" * 50)
        self.assertEqual(status, 422)
        self.assertEqual(body["ok"], False)

    def test_too_large_413(self):
        status, body = self.photo(body=b"\xff\xd8" + b"\x00" * (1048576 - 1))
        self.assertEqual(status, 413)
        self.assertEqual(body["ok"], False)
        status, _ = self.photo(body=b"\xff\xd8" + b"\x00" * (1048576 - 2))
        self.assertEqual(status, 201)  # exactly the limit is accepted

    def test_wrong_content_type_415(self):
        status, body = self.photo(ctype="application/octet-stream")
        self.assertEqual(status, 415)
        self.assertEqual(body["ok"], False)

    def test_bad_photo_n_and_visit_400(self):
        for n in ("0", "6", "x", ""):
            status, _ = self.photo(n=n)
            self.assertEqual(status, 400, n)
        status, _ = self.photo(visit="../evil")
        self.assertEqual(status, 400)

    def test_visit_incomplete_flag(self):
        visit = "ps-01-20261103T101500Z-0042"
        self.photo(visit=visit, n="1")
        meta = {"station_id": "ps-01", "visit_id": visit,
                "photos": [{"n": 1, "bytes": 104}, {"n": 2, "bytes": 104}]}
        status, body = self.post_json("/api/photostation/visit", meta)
        self.assertEqual(status, 201)
        self.assertTrue(body["ok"])
        self.assertIs(body["incomplete"], True)
        self.assertTrue(os.path.exists(os.path.join(self.store, visit, "visit.json")))
        self.photo(visit=visit, n="2")
        status, body = self.post_json("/api/photostation/visit", meta)
        self.assertEqual(status, 200)
        self.assertIs(body["incomplete"], False)

    def test_fail_mode_then_recover(self):
        status, _ = self.request("/__mode", b'{"fail": 2}', {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(self.photo()[0], 503)
        self.assertEqual(self.photo()[0], 503)
        self.assertEqual(self.photo()[0], 201)

    def test_mode_too_large_413(self):
        status, _ = self.request("/__mode", b" " * (1048576 + 1), {"Content-Type": "application/json"})
        self.assertEqual(status, 413)

    def test_heartbeat_appends(self):
        self.assertEqual(self.post_json("/api/photostation/heartbeat", {"uptime": 1})[0], 200)
        self.assertEqual(self.post_json("/api/photostation/heartbeat", {"uptime": 2})[0], 200)
        with open(os.path.join(self.store, "heartbeat.jsonl")) as f:
            lines = [json.loads(line) for line in f]
        self.assertEqual([x["uptime"] for x in lines], [1, 2])
        self.assertEqual(self.post_json("/api/photostation/heartbeat", {}, key="bad")[0], 401)


if __name__ == "__main__":
    unittest.main()
