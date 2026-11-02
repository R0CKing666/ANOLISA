"""Regression checks for package-manager selection in the Hermes installer.

The installer used to recognise only ``fedora`` as a dnf host.  Every other
RHEL-family distribution (rhel, centos, rocky, alma, alinux, anolis) fell
through to the generic "use your package manager" branch, so ripgrep and
ffmpeg were never installed and operators were told to install them by hand.

The installer runs as a whole script, so the test drives it with stub tools on
a PATH that contains no ripgrep/ffmpeg, and points ``HERMES_OS_RELEASE_FILE``
at a minimal os-release file to select the distribution.

The run always stops in ``clone_repo`` (the install directory is a plain,
non-git directory), which keeps the test offline and deterministic.
"""

import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "ai/install-hermes/scripts/install.sh"

# Tools the installer reaches before clone_repo().  ``id`` is stubbed to report
# uid 0 so the "already root" package-install branch runs regardless of the
# user running the tests; ``uname`` and ``awk`` are the real binaries.
STUBS = {
    "uv": """#!/bin/sh
case "$1" in
  --version) echo "uv 0.5.0" ;;
  python) echo "python3" ;;
esac
""",
    "python3": """#!/bin/sh
if [ "$1" = "--version" ]; then echo "Python 3.11.9"; fi
""",
    "git": """#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "git version 2.43.0"
else
  exit 1
fi
""",
    "node": """#!/bin/sh
if [ "$1" = "--version" ]; then echo "v22.11.0"; fi
""",
    "id": """#!/bin/sh
if [ "$1" = "-u" ]; then echo 0; else echo "uid=0(root) gid=0(root)"; fi
""",
    "dnf": """#!/bin/sh
echo "$*" >> "$DNF_LOG"
exit "${DNF_EXIT:-0}"
""",
}

REAL_TOOLS = ("uname", "awk")


@unittest.skipUnless(platform.system() == "Linux", "installer only dispatches package managers on Linux")
class InstallerPackageManagerTests(unittest.TestCase):
    def setUp(self):
        self.bash = shutil.which("bash")
        if self.bash is None:
            self.skipTest("bash is required to run the installer")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.tmp = Path(self.temporary.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, body in STUBS.items():
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)
        for name in REAL_TOOLS:
            real = shutil.which(name)
            if real is None:
                self.skipTest(f"{name} is required to run the installer")
            os.symlink(real, self.bin / name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.install_dir = self.home / ".hermes/hermes-agent"
        self.install_dir.mkdir(parents=True)
        self.log = self.tmp / "dnf.log"

    def run_installer(self, distro, dnf_exit=0):
        os_release = self.tmp / f"os-release-{distro}"
        os_release.write_text(f"ID={distro}\n")
        env = {
            "PATH": str(self.bin),
            "HOME": str(self.home),
            "HERMES_HOME": str(self.home / ".hermes"),
            "HERMES_INSTALL_DIR": str(self.install_dir),
            "HERMES_OS_RELEASE_FILE": str(os_release),
            "DNF_LOG": str(self.log),
            "DNF_EXIT": str(dnf_exit),
            "LANG": "C",
            "TERM": "dumb",
        }
        result = subprocess.run(
            [self.bash, str(INSTALLER)],
            capture_output=True,
            text=True,
            env=env,
            stdin=subprocess.DEVNULL,
            timeout=120,
        )
        # clone_repo() stops the run deterministically once the package step is
        # over; anything else means the installer never reached that point.
        self.assertIn("is not a git repository", result.stdout + result.stderr)
        return result

    def dnf_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_dnf_family_installs_ripgrep_and_ffmpeg(self):
        for distro in ("fedora", "rhel", "centos", "rocky", "alma", "alinux", "anolis"):
            with self.subTest(distro=distro):
                self.log.unlink(missing_ok=True)
                result = self.run_installer(distro)
                self.assertEqual(self.dnf_calls(), ["install -y ripgrep ffmpeg"])
                self.assertIn("ripgrep installed", result.stdout)
                self.assertIn("ffmpeg installed", result.stdout)

    def test_dnf_failure_prints_dnf_manual_hint(self):
        result = self.run_installer("alinux", dnf_exit=1)
        self.assertIn("sudo dnf install ripgrep", result.stdout)
        self.assertIn("sudo dnf install ffmpeg", result.stdout)

    def test_unknown_distro_does_not_use_dnf(self):
        result = self.run_installer("void")
        self.assertEqual(self.dnf_calls(), [])
        self.assertIn("Use your package manager", result.stdout)

    def test_installer_parses(self):
        result = subprocess.run(
            [self.bash, "-n", str(INSTALLER)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
