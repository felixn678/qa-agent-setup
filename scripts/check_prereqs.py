"""Check (and with --install, fix) the machine prerequisites for the QA agent.

Usage: python3 check_prereqs.py [--install] [--json]
  (no flag)  report only, changes nothing
  --install  install the missing pieces that can be installed safely (PyYAML, Playwright package);
             anything else is printed as an exact command for the user
Checks: python3 >= 3.9, PyYAML, node >= 18, npm, Playwright package, a Chromium browser (Edge/Chrome),
git. Needs no third-party package itself. Exit code 1 when a required item is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys

OS = platform.system()  # Darwin | Linux | Windows
results: list[dict] = []


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=(OS == "Windows"))
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def add(name: str, ok: bool, detail: str, required: bool, fix_cmd: str = "", auto: bool = False) -> None:
    results.append({"name": name, "ok": ok, "detail": detail, "required": required, "fix": fix_cmd, "auto": auto})


def brew_or(mac: str, other: str) -> str:
    return mac if OS == "Darwin" and shutil.which("brew") else other


def check() -> None:
    v = sys.version_info
    add("python3", v >= (3, 9), f"{v.major}.{v.minor}.{v.micro}", True,
        brew_or("brew install python", "install Python 3.9+ from https://www.python.org/downloads/"))

    try:
        import yaml  # noqa: F401
        add("PyYAML", True, f"v{getattr(yaml, '__version__', '?')}", True)
    except ImportError:
        add("PyYAML", False, "missing", True, f'"{sys.executable}" -m pip install --user pyyaml', auto=True)

    node = shutil.which("node")
    nv = run(["node", "-v"])[1] if node else ""
    major = int(nv.lstrip("v").split(".")[0]) if nv.startswith("v") and nv[1:2].isdigit() else 0
    add("node", major >= 18, nv or "missing", True, brew_or("brew install node", "install Node 18+ from https://nodejs.org"))
    add("npm", bool(shutil.which("npm")), "found" if shutil.which("npm") else "missing", True, "comes with Node")

    pw = False
    if shutil.which("npm"):
        code, out = run(["npm", "ls", "-g", "--depth=0", "playwright"])
        pw = code == 0 and "playwright@" in out
    add("playwright", pw, "installed" if pw else "missing (needed to test screens)", False, "npm install -g playwright", auto=True)

    browsers = {"Darwin": ["/Applications/Microsoft Edge.app", "/Applications/Google Chrome.app"],
                "Windows": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
                "Linux": []}[OS]
    found = [pathlib.Path(b).name for b in browsers if os.path.exists(b)]
    found += [n for n in ("microsoft-edge", "google-chrome", "chromium") if shutil.which(n)]
    add("browser (Edge/Chrome)", bool(found), ", ".join(found) or "none found", False,
        brew_or("brew install --cask google-chrome", "install Microsoft Edge or Google Chrome"))

    add("git", bool(shutil.which("git")), "found" if shutil.which("git") else "missing", False, brew_or("brew install git", "install git from https://git-scm.com"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    check()
    if a.install:
        for r in [r for r in results if not r["ok"] and r["auto"]]:
            print(f"installing {r['name']} ...", file=sys.stderr)
            run(r["fix"].replace('"', "").split() if r["name"] != "PyYAML" else [sys.executable, "-m", "pip", "install", "--user", "pyyaml"], timeout=600)
        results.clear()
        check()
    bad_required = [r for r in results if not r["ok"] and r["required"]]
    if a.json:
        print(json.dumps({"ready": not bad_required, "checks": results}, indent=2))
    else:
        for r in results:
            print(f"{'OK  ' if r['ok'] else ('MISS' if r['required'] else 'WARN')}  {r['name']}: {r['detail']}")
            if not r["ok"]:
                print(f"      fix: {r['fix']}" + ("   (can auto-install)" if r["auto"] else ""))
        print("READY" if not bad_required else "NOT READY: install the MISS items above")
    sys.exit(1 if bad_required else 0)


if __name__ == "__main__":
    main()
