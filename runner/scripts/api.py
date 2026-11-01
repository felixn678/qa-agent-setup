"""Call a backend service of the project under test, never printing the token.

Resolves the base URL from .qa/qa.config.yaml (backend.services.<service>.base_url) and the
auth header from backend.auth. A `local` environment maps to environments.<env>.backend_env
(the backend a locally running frontend talks to).

CLI:    python api.py <service> <env> <path> [--method POST] [--data '{"a":1}' | --data-file body.json]
                      [--version v2] [--save out.xlsx]
        Pass <path> without the leading slash on Git Bash/MSYS (it rewrites a leading slash).
Import: from api import Client; c = Client("orders", "dev"); status, headers, body = c.get("/health")
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

import qa_config


class Client:
    def __init__(self, service: str, env: str, version: str | None = None):
        cfg, root = qa_config.load()
        env_cfg = (cfg.get("environments", {}).get("list", {}) or {}).get(env, {}) or {}
        env = env_cfg.get("backend_env", env)
        services = cfg.get("backend", {}).get("services", {})
        if service not in services:
            raise SystemExit(f"service '{service}' not in backend.services (known: {', '.join(services) or 'none'})")
        base = services[service]["base_url"]
        try:
            base = base[version][env] if version else base[env]
        except KeyError:
            raise SystemExit(f"no base_url for service '{service}' version '{version or '-'}' env '{env}' in qa.config.yaml")
        if not base:
            raise SystemExit(f"base_url for {service}/{version or ''}/{env} is empty in qa.config.yaml")
        self.base = base.rstrip("/")
        self._headers: dict[str, str] = {}
        auth = cfg.get("backend", {}).get("auth") or {}
        if auth.get("type", "header") != "none":
            token = qa_config.resolve_secret(auth, root)
            if not token:
                hint = " (optional: skip API checks and test on screen)" if auth.get("type") == "optional" else ""
                raise SystemExit(f"{auth.get('env_var')} is not set{hint}; see backend.auth in qa.config.yaml")
            self._headers[auth["header_name"]] = auth["header_format"].format(token=token)

    def get(self, path: str, save: str | None = None):
        return self.request("GET", path, save=save)

    def request(self, method: str, path: str, json_body=None, save: str | None = None):
        headers = dict(self._headers)
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + "/" + path.lstrip("/"), data=data, headers=headers, method=method.upper())
        try:
            resp = urllib.request.urlopen(req, timeout=180)
            status, resp_headers, body = resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            status, resp_headers, body = e.code, dict(e.headers), e.read()
        resp_headers = {k.lower(): v for k, v in resp_headers.items()}
        if save and status == 200:
            pathlib.Path(save).write_bytes(body)
        return status, resp_headers, body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("service")
    parser.add_argument("env")
    parser.add_argument("path")
    parser.add_argument("--version")
    parser.add_argument("--save")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--data", help="JSON request body")
    parser.add_argument("--data-file", help="file holding the JSON request body")
    args = parser.parse_args()

    raw = pathlib.Path(args.data_file).read_text(encoding="utf-8") if args.data_file else args.data
    body_json = json.loads(raw) if raw else None
    status, headers, body = Client(args.service, args.env, args.version).request(
        args.method, args.path, json_body=body_json, save=args.save
    )
    ctype = headers.get("content-type", "")
    line = f"{args.method.upper()} {args.path} -> {status} | {ctype} | {headers.get('content-disposition', '-')} | {len(body)} bytes"
    if "json" in ctype or "text" in ctype:
        line += "\n" + body[:2000].decode("utf-8", "replace")
    elif args.save and status == 200:
        line += f"\nsaved to {args.save}"
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
