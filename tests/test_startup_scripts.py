from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StartupScriptTests(unittest.TestCase):
    def test_start_dev_waits_for_backend_health_before_opening_browser(self):
        script = (ROOT / "start_dev.bat").read_text(encoding="utf-8")

        wait_health = script.index("scripts\\wait_http.ps1")
        wait_frontend = script.index("scripts\\wait_listen.ps1")
        open_browser = script.index("start http://127.0.0.1:3000")

        self.assertLess(wait_health, wait_frontend)
        self.assertLess(wait_frontend, open_browser)
        self.assertIn("http://127.0.0.1:8000/api/v1/health", script)

    def test_dev_stack_open_browser_waits_for_backend_health(self):
        script = (ROOT / "scripts" / "dev_stack.ps1").read_text(encoding="utf-8")

        self.assertIn("Wait-HttpReady", script)
        self.assertIn("http://127.0.0.1:8000/api/v1/health", script)
        self.assertIn('Start-Process "http://127.0.0.1:3000"', script)


if __name__ == "__main__":
    unittest.main()
