"""End-to-end checks for the local website's HTTP interface."""

import json
import shutil
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from webapp.server import Handler


class WebAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def post(self, payload):
        request = Request(
            self.base + "/api/compile",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_home_page_and_compiler_stages(self):
        with urlopen(self.base, timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn("The compiler workspace", page)
        status, data = self.post({"source": "BEGIN\nDECLARE x AS INTEGER\nSET x = 2 + 3\nPRINT x\nEND"})
        self.assertEqual(status, 200)
        self.assertIn("x = 5;", data["stages"]["c"])
        self.assertIn("t1 = 2 + 3", data["stages"]["ir"])

    def test_source_error_is_reported_without_c(self):
        status, data = self.post({"source": "BEGIN\nSET y = 3\nEND"})
        self.assertEqual(status, 422)
        self.assertIn("undeclared identifier 'y'", data["error"])
        self.assertNotIn("stages", data)

    def test_cross_origin_compile_request_is_rejected(self):
        request = Request(
            self.base + "/api/compile",
            data=json.dumps({"source": "BEGIN\nEND"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": "https://example.org"},
        )
        with self.assertRaises(HTTPError) as result:
            urlopen(request, timeout=5)
        self.assertEqual(result.exception.code, 403)

    @unittest.skipUnless(shutil.which("gcc"), "GCC is required to run generated C")
    def test_run_generated_c_and_report_runtime_guard(self):
        source = ("BEGIN\nDECLARE a AS INTEGER\nDECLARE b AS INTEGER\n"
                  "READ a\nREAD b\nPRINT a / b\nEND")
        status, data = self.post({"source": source, "input": "20 0", "run": True})
        self.assertEqual(status, 200)
        self.assertEqual(data["execution"]["exit_code"], 1)
        self.assertIn("Division or remainder by zero", data["execution"]["stderr"])


if __name__ == "__main__":
    unittest.main()
