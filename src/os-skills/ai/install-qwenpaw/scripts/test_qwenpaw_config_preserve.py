#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Re-running setup.sh must keep a user-edited config.json."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("setup.sh")

STUBS = {
    "uv": '#!/bin/sh\n[ "$1" = "--version" ] && echo "uv test"\nexit 0\n',
    "qwenpaw": '#!/bin/sh\n[ "$1" = "--version" ] && echo "qwenpaw test"\nexit 0\n',
    "curl": '#!/bin/sh\necho 200\nexit 0\n',
    "pgrep": '#!/bin/sh\nexit 1\n',
    "sleep": '#!/bin/sh\nexit 0\n',
}


@unittest.skipUnless(
    os.name == "posix" and shutil.which("bash"), "requires bash on POSIX"
)
class ConfigPreservationTests(unittest.TestCase):
    def make_stubs(self, root: Path) -> Path:
        bin_dir = root / "bin"
        bin_dir.mkdir()
        for name, body in STUBS.items():
            path = bin_dir / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        return bin_dir

    def run_setup(self, home: Path, bin_dir: Path) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "HOME": str(home),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        }
        return subprocess.run(
            ["bash", str(SCRIPT), "sk-test", "dingtest", "secrettest"],
            env=env, capture_output=True, text=True, timeout=120,
        )

    def test_existing_config_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            bin_dir = self.make_stubs(root)

            first = self.run_setup(home, bin_dir)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            config = home / ".qwenpaw" / "config.json"
            self.assertTrue(config.is_file())

            data = json.loads(config.read_text(encoding="utf-8"))
            data["agents"]["defaults"]["heartbeat"] = {"enabled": True, "every": "30m"}
            data["telegram"] = {"enabled": True, "token": "user-set"}
            config.write_text(json.dumps(data), encoding="utf-8")

            second = self.run_setup(home, bin_dir)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            after = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(
                after["agents"]["defaults"]["heartbeat"],
                {"enabled": True, "every": "30m"},
            )
            self.assertEqual(after["telegram"], {"enabled": True, "token": "user-set"})


if __name__ == "__main__":
    unittest.main()
