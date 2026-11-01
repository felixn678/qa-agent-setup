"""Scan a project and print what the QA setup interview can pre-fill, as JSON.

Facts only, no decisions. Never prints values of keys that look secret (token, secret, key,
password, credential); for .env files only URL/host/port-like keys are reported.

Usage: python detect_project.py [project-root]   (default: cwd)
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
SECRET_KEY = re.compile(r"token|secret|key|passw|credential|private", re.I)
URLISH_KEY = re.compile(r"url|host|port|origin|endpoint|api|base|domain", re.I)
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "venv", ".venv", "__pycache__", "coverage", "target"}


def read(path: pathlib.Path, limit: int = 400_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def walk(max_depth: int = 4):
    base_depth = len(ROOT.parts)
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") or d in (".github", ".qa")]
        if len(pathlib.Path(dirpath).parts) - base_depth >= max_depth:
            dirs[:] = []
        for name in files:
            yield pathlib.Path(dirpath) / name


def rel(p: pathlib.Path) -> str:
    return str(p.relative_to(ROOT))


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def node_info(out: dict) -> None:
    pkg_path = ROOT / "package.json"
    if not pkg_path.is_file():
        return
    try:
        pkg = json.loads(read(pkg_path))
    except ValueError:
        return
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    has = lambda *names: [n for n in names if n in deps]
    out["node"] = {
        "name": pkg.get("name"),
        "package_manager": next((m for f, m in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("package-lock.json", "npm")) if (ROOT / f).exists()), "npm"),
        "scripts": {k: v for k, v in pkg.get("scripts", {}).items() if re.search(r"start|dev|serve|test|e2e|build|lint", k)},
        "frontend_frameworks": has("react", "next", "vue", "nuxt", "@angular/core", "svelte", "solid-js", "react-native", "expo"),
        "bundlers": has("vite", "webpack", "react-scripts", "parcel", "turbo"),
        "ui_test_tools": has("@playwright/test", "playwright", "cypress", "puppeteer", "selenium-webdriver"),
        "unit_test_tools": has("vitest", "jest", "mocha", "@testing-library/react"),
        "backend_frameworks": has("express", "@nestjs/core", "fastify", "koa", "hono"),
        "auth_libs": has("@azure/msal-browser", "@azure/msal-react", "@auth0/auth0-react", "next-auth", "keycloak-js", "firebase", "@okta/okta-react", "@clerk/clerk-react", "@supabase/supabase-js", "oidc-client-ts", "better-auth", "passport"),
        "feature_flags": has("posthog-js", "launchdarkly-js-client-sdk", "@growthbook/growthbook-react", "unleash-proxy-client"),
    }
    ports = set()
    for script in pkg.get("scripts", {}).values():
        ports.update(re.findall(r"(?:--port[= ]|PORT=|-p )(\d{4,5})", script))
    out["node"]["ports_in_scripts"] = sorted(ports)


def python_java_go(out: dict) -> None:
    text = read(ROOT / "pyproject.toml") + read(ROOT / "requirements.txt") + read(ROOT / "Pipfile")
    backends = [n for n in ("fastapi", "django", "flask", "starlette", "aiohttp", "tornado") if re.search(rf"\b{n}\b", text, re.I)]
    if backends:
        out["python_backend"] = backends
    if (ROOT / "pom.xml").exists() or list(ROOT.glob("build.gradle*")):
        out["jvm"] = "spring" if re.search("spring", read(ROOT / "pom.xml") + "".join(read(p) for p in ROOT.glob("build.gradle*")), re.I) else "jvm"
    if (ROOT / "go.mod").exists():
        out["go"] = True
    if list(ROOT.glob("*.csproj")) or list(ROOT.glob("*/*.csproj")):
        out["dotnet"] = True


def env_files(out: dict) -> None:
    found = {}
    for path in walk(3):
        if re.match(r"\.env(\..+)?$|.*\.env$", path.name) or path.name.startswith(".env"):
            keys = {}
            for line in read(path).splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if SECRET_KEY.search(key):
                        keys[key] = "<secret: not shown>"
                    elif URLISH_KEY.search(key):
                        keys[key] = value.strip().strip('"').strip("'")[:120]
            found[rel(path)] = {"url_like_keys": keys, "tracked_by_git": bool(sh(["git", "ls-files", rel(path)]).strip())}
    if found:
        out["env_files"] = found


def api_specs(out: dict) -> None:
    specs = [rel(p) for p in walk(4) if re.match(r"(openapi|swagger).*\.(json|ya?ml)$", p.name, re.I)]
    if specs:
        out["openapi_files"] = specs[:10]
    hint = []
    for path in list(walk(3))[:3000]:
        if path.suffix in (".py", ".ts", ".js", ".java", ".cs") and re.search(r"/(docs|swagger|openapi\.json|api-docs)\b", read(path, 20000)):
            hint.append(rel(path))
            if len(hint) >= 5:
                break
    if hint:
        out["swagger_route_hints"] = hint


def compose(out: dict) -> None:
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        text = read(ROOT / name)
        if text:
            out["docker_compose"] = {"file": name, "ports": sorted(set(re.findall(r'"?(\d{2,5}):\d{2,5}"?', text)))[:15],
                                     "services": re.findall(r"^  ([\w-]+):\s*$", text, re.M)[:15]}
            return


def routes(out: dict) -> None:
    found = []
    for path in walk(5):
        if path.suffix in (".tsx", ".ts", ".jsx", ".js", ".vue") and re.search(r"route|router|app", path.name, re.I):
            for m in re.finditer(r"""path:\s*["'`](/[^"'`]*)["'`]|<Route[^>]*path=["'`](/[^"'`]*)["'`]""", read(path, 60000)):
                found.append(m.group(1) or m.group(2))
    next_dirs = [p for p in ("app", "src/app", "pages", "src/pages") if (ROOT / p).is_dir()]
    if found:
        out["routes_sample"] = sorted(set(found))[:40]
    if next_dirs:
        out["file_based_routing_dirs"] = next_dirs


def git_info(out: dict) -> None:
    remote = sh(["git", "remote", "get-url", "origin"]).strip()
    branches = sh(["git", "branch", "-a", "--format=%(refname:short)"]).split()[:200]
    subjects = sh(["git", "log", "-60", "--format=%s"]).splitlines()
    sample = " ".join(branches + subjects)
    patterns = {
        "azure_ab": len(re.findall(r"AB#\d+", sample)),
        "jira_like": len(re.findall(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b", sample)),
        "github_hash": len(re.findall(r"(?<![\w&])#\d{1,6}\b", sample)),
        "clickup_cu": len(re.findall(r"\bCU-[a-z0-9]+\b", sample)),
        "numeric_ids_in_branches": len(re.findall(r"(?:feat|fix|bug|task)/\d{3,6}\b", " ".join(branches))),
    }
    host = next((h for h, pat in (("azure-devops", "dev.azure.com|visualstudio.com"), ("github", "github.com"), ("gitlab", "gitlab"), ("bitbucket", "bitbucket")) if re.search(pat, remote)), None)
    out["git"] = {"remote_host": host, "remote": re.sub(r"//[^@/]+@", "//", remote), "current_branch": sh(["git", "branch", "--show-current"]).strip(),
                  "ticket_pattern_counts": patterns, "default_branches": [b for b in branches if b.endswith(("main", "master", "develop", "development", "stage", "staging"))][:8]}


def agent_files(out: dict) -> None:
    out["agent_files"] = [n for n in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".github/copilot-instructions.md", ".claude", ".codex", ".cursor") if (ROOT / n).exists()]
    out["ci"] = [rel(p) for p in walk(3) if p.name in ("azure-pipelines.yml", "Jenkinsfile", ".gitlab-ci.yml", "bitbucket-pipelines.yml") or (p.parent.name == "workflows" and p.suffix in (".yml", ".yaml"))][:6]
    out["docs"] = [n for n in ("README.md", "docs", "CONTRIBUTING.md") if (ROOT / n).exists()]
    out["existing_qa_config"] = (ROOT / ".qa" / "qa.config.yaml").is_file()
    out["vpn_hints"] = [rel(p) for p in walk(2) if p.name in ("README.md", "CLAUDE.md", "AGENTS.md") and re.search(r"\bvpn\b", read(p, 50000), re.I)]


def tools(out: dict) -> None:
    candidates = ("node", "npm", "npx", "python3", "az", "gh", "glab", "jira", "claude", "codex", "gemini", "docker", "curl")
    out["tools_on_path"] = {c: bool(shutil.which(c)) for c in candidates}
    mac = {"edge": "/Applications/Microsoft Edge.app", "chrome": "/Applications/Google Chrome.app", "firefox": "/Applications/Firefox.app"}
    out["browsers"] = {k: (pathlib.Path(v).exists() if sys.platform == "darwin" else bool(shutil.which({"edge": "microsoft-edge", "chrome": "google-chrome", "firefox": "firefox"}[k]))) for k, v in mac.items()}
    npx_pw = sh(["npx", "--no-install", "playwright", "--version"]).strip()
    out["playwright_global_or_local"] = npx_pw or None


def main() -> None:
    out: dict = {"root": str(ROOT)}
    for step in (node_info, python_java_go, env_files, api_specs, compose, routes, git_info, agent_files, tools):
        try:
            step(out)
        except Exception as exc:  # detection must never abort the interview
            out.setdefault("detection_errors", []).append(f"{step.__name__}: {exc}")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
