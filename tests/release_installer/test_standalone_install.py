#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Release installer acceptance: standalone ZIP bootstrap + doctor status contract.

Runs entirely offline with a fresh HOME/work dir. Verifies:
  - build_release ZIP embeds install.py + matching installer_sha256
  - a stranger can bootstrap from the ZIP alone (no repo checkout)
  - installer --version reflects the single-source version
  - doctor distinguishes ok / not_installed / unowned / incomplete /
    launcher_failed / version_mismatch, and an empty data root is not a failure
  - update preserves user data; uninstall preserves data; reinstall works
  - deleting the original ZIP and temp dir leaves the Skill runnable
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "tools" / "install.py"
BUILD = ROOT / "tools" / "build_release.py"
VERSION_PY = ROOT / "src" / "skill_interface" / "version.py"
PY = sys.executable


def release_version() -> str:
    for line in VERSION_PY.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("RELEASE_VERSION") and "=" in s:
            return s.split("=", 1)[1].strip().strip('"\'')
    raise AssertionError("RELEASE_VERSION not found")


def run(args, env=None):
    e = dict(os.environ)
    e.pop("SOURCELORE_PROJECT_ROOT", None)
    e.pop("SOURCELORE_SKILL_DIR", None)
    if env:
        e.update(env)
    return subprocess.run(args, capture_output=True, text=True, env=e, timeout=90)


def js(run_result):
    return json.loads(run_result.stdout)


class TestStandaloneZipBootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ver = release_version()
        cls.tmp = Path(tempfile.mkdtemp(prefix="sl-standalone-"))
        cls.dist = cls.tmp / "dist"
        r = run([PY, str(BUILD), "--out", str(cls.dist)])
        assert r.returncode == 0, r.stderr + r.stdout
        cls.zip = cls.dist / f"sourcelore-skill-v{cls.ver}.zip"
        assert cls.zip.is_file(), "release ZIP not built"
        manifest = json.loads((cls.dist / "RELEASE_INFO.json").read_text(encoding="utf-8"))
        with zipfile.ZipFile(cls.zip) as z:
            names = z.namelist()
            cls.embedded_installer = z.read("sourcelore/install.py")
            embedded_info = json.loads(z.read("sourcelore/RELEASE_INFO.json"))
        assert "sourcelore/install.py" in names, "ZIP must embed install.py"
        assert "sourcelore/_sourcelore_src/src/skill_interface/cli.py" in names
        assert embedded_info.get("installer") == "install.py"
        import hashlib
        assert embedded_info["installer_sha256"] == hashlib.sha256(cls.embedded_installer).hexdigest()
        assert embedded_info["version"] == cls.ver

    def _env(self, skill, data):
        return {"HOME": str(self.tmp / "home"), "SOURCELORE_DATA_ROOT": str(data)}

    def test_installer_version_matches_release(self):
        # Running the installer that is *inside* the ZIP reports the release version.
        staged = self.tmp / "embedded-installer.py"
        staged.write_bytes(self.embedded_installer)
        r = run([PY, str(staged), "--version"])
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(js(r)["installer_version"], self.ver)

    def test_zip_only_bootstrap_and_delete_zip(self):
        base = self.tmp / "case_bootstrap"
        skill = base / "skills" / "sourcelore"
        data = base / "data"
        base.mkdir(parents=True, exist_ok=True)
        env = self._env(skill, data)
        # Stranger flow: download the ZIP, extract it, run the installer that
        # lives at the ZIP root with NO --source / --zip and NO repo checkout.
        downloaded = base / "downloaded.zip"
        downloaded.write_bytes(self.zip.read_bytes())
        extracted = base / "extracted"
        with zipfile.ZipFile(downloaded) as z:
            z.extractall(extracted)
        embedded_installer = extracted / "sourcelore" / "install.py"
        self.assertTrue(embedded_installer.is_file())
        r = run([PY, str(embedded_installer), "install"], env=env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        # Without --skill-dir the installer uses $HOME/.agents/skills/sourcelore.
        installed = self.tmp / "home" / ".agents" / "skills" / "sourcelore"
        self.assertTrue((installed / "SKILL.md").is_file(), r.stdout + r.stderr)

        launcher = installed / "scripts" / "sourcelore.py"
        v = run([PY, str(launcher), "--version"], env=env)
        self.assertEqual(v.returncode, 0, v.stderr + v.stdout)
        self.assertEqual(json.loads(v.stdout)["skill_version"], self.ver)
        h = run([PY, str(launcher), "--help"], env=env)
        self.assertEqual(h.returncode, 0, h.stderr + h.stdout)

        # Delete the downloaded ZIP and the entire extraction directory.
        downloaded.unlink()
        shutil.rmtree(extracted)
        self.assertFalse(downloaded.exists())
        self.assertFalse(extracted.exists())
        v2 = run([PY, str(launcher), "--version"], env=env)
        self.assertEqual(v2.returncode, 0, v2.stderr + v2.stdout)
        self.assertFalse(data.exists(), "install must not create the knowledge data root")

    def test_update_preserves_data_and_uninstall_reinstall(self):
        base = self.tmp / "case_update"
        skill = base / "skills" / "sourcelore"
        data = base / "data"
        data.mkdir(parents=True)
        sentinel = data / "USERDATA-SENTINEL"
        sentinel.write_text("keep-me", encoding="utf-8")
        env = self._env(skill, data)
        r = run([PY, str(INSTALLER), "install", "--zip", str(self.zip),
                 "--skill-dir", str(skill)], env=env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        sentinel.write_text("keep-me", encoding="utf-8")

        u = run([PY, str(INSTALLER), "update", "--zip", str(self.zip),
                 "--skill-dir", str(skill)], env=env)
        self.assertEqual(u.returncode, 0, u.stderr + u.stdout)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep-me")

        d = run([PY, str(INSTALLER), "uninstall", "--skill-dir", str(skill)], env=env)
        self.assertEqual(d.returncode, 0, d.stderr + d.stdout)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep-me")
        self.assertFalse(skill.exists())

        r2 = run([PY, str(INSTALLER), "install", "--zip", str(self.zip),
                  "--skill-dir", str(skill)], env=env)
        self.assertEqual(r2.returncode, 0, r2.stderr + r2.stdout)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep-me")


class TestDoctorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="sl-doctor-"))
        cls.ver = release_version()
        cls.base = cls.tmp / "dist"
        r = run([PY, str(BUILD), "--out", str(cls.base)])
        assert r.returncode == 0, r.stderr + r.stdout
        cls.zip = cls.base / f"sourcelore-skill-v{cls.ver}.zip"

    def _doctor(self, skill, data, extra=None, env=None):
        e = {"SOURCELORE_DATA_ROOT": str(data)}
        if env:
            e.update(env)
        args = [PY, str(INSTALLER), "doctor", "--skill-dir", str(skill), "--json"]
        if extra:
            args += extra
        r = run(args, env=e)
        return r, js(r)

    def _install(self, skill):
        r = run([PY, str(INSTALLER), "install", "--zip", str(self.zip),
                 "--skill-dir", str(skill)],
                env={"SOURCELORE_DATA_ROOT": str(self.tmp / "data")})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_not_installed(self):
        r, d = self._doctor(self.tmp / "none", self.tmp / "data")
        self.assertEqual(d["status"], "not_installed")
        self.assertFalse(d["ok"])
        self.assertFalse(d["healthy"])
        self.assertEqual(r.returncode, 1)

    def test_ok_with_empty_data_root(self):
        skill = self.tmp / "ok-skill"
        self._install(skill)
        r, d = self._doctor(skill, self.tmp / "empty-data")
        self.assertEqual(d["status"], "ok", d)
        self.assertTrue(d["ok"])
        self.assertTrue(d["healthy"])
        self.assertEqual(r.returncode, 0)
        self.assertEqual(d["data_root_status"], "not_created")

    def test_unowned_dir(self):
        d0 = self.tmp / "unowned"
        d0.mkdir(parents=True)
        r, d = self._doctor(d0, self.tmp / "data")
        self.assertEqual(d["status"], "unowned")
        self.assertFalse(d["ok"])
        self.assertEqual(r.returncode, 1)

    def test_incomplete(self):
        skill = self.tmp / "incomplete"
        self._install(skill)
        (skill / "scripts" / "sourcelore.py").unlink()
        r, d = self._doctor(skill, self.tmp / "data")
        self.assertEqual(d["status"], "incomplete")
        self.assertFalse(d["ok"])
        self.assertEqual(r.returncode, 1)

    def test_launcher_failed(self):
        skill = self.tmp / "badlauncher"
        self._install(skill)
        launcher = skill / "scripts" / "sourcelore.py"
        launcher.write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
        r, d = self._doctor(skill, self.tmp / "data")
        self.assertEqual(d["status"], "launcher_failed")
        self.assertFalse(d["ok"])
        self.assertEqual(r.returncode, 1)

    def test_version_mismatch(self):
        skill = self.tmp / "mismatch"
        self._install(skill)
        r, d = self._doctor(skill, self.tmp / "data",
                            extra=["--expect-version", "0.0.0-wrong"])
        self.assertEqual(d["status"], "version_mismatch")
        self.assertFalse(d["ok"])
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
