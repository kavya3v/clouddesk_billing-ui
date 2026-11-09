import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.__main__ import start, DEFAULT_ENV_FILE

class StartupTests(unittest.TestCase):
    def test_default_env_is_project_root(self):
        self.assertEqual(DEFAULT_ENV_FILE,Path(__file__).resolve().parents[1]/".env")

    @patch.dict("os.environ",{"FIREWORKS_API_KEY":"stale"},clear=True)
    @patch("backend.__main__.uvicorn.run")
    def test_saved_env_overrides_stale_process_value_before_start(self,run):
        with tempfile.TemporaryDirectory() as directory:
            env=Path(directory)/".env"
            env.write_text("FIREWORKS_API_KEY=fake-saved-value\n",encoding="utf-8")
            run.side_effect=lambda *a,**kw:self.assertEqual(os.environ["FIREWORKS_API_KEY"],"fake-saved-value")
            start(env)
        run.assert_called_once_with("backend.main:app",host="127.0.0.1",port=8000)
