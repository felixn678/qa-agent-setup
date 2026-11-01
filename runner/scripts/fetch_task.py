"""Fetch a task/ticket from the configured tracker and print it as normalized plain text.

The tracker comes from .qa/qa.config.yaml -> task_source.type:
  azure-devops | jira | clickup | github | linear | manual
Read-only: this script never writes to the tracker. Secrets are read from the env var named in
task_source.auth.env_var (or a CLI such as `az`/`gh` that is already logged in) and never printed.

Usage:  python fetch_task.py <id | url | path-to-text-file | -> [--save out.json] [--config path]
Output: type/title/state/labels/area, then DESCRIPTION, ACCEPTANCE CRITERIA, IMAGES, LINKS.
        --save writes the same data as JSON: {id,url,type,title,state,labels,area,description,
        acceptance_criteria,images,links,raw}
For `manual`, the argument is a file (or `-` for stdin) holding the description; image paths/URLs
found in it, or listed under task_source.images, are reported under IMAGES.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

import qa_config

AC_HEADING = re.compile(r"^\s*#*\s*\**\s*(acceptance criteria|criteria|expected (?:result|behaviou?r))\s*\**\s*:?\s*$", re.I)


def html_to_text(value: str | None) -> str:
    text = re.sub(r"<br\s*/?>|</(p|li|div|pre|h\d|tr)>", "\n", value or "")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def split_acceptance(text: str) -> tuple[str, str]:
    """Split a free-text description at an 'Acceptance Criteria' heading. Returns (description, criteria)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if AC_HEADING.match(line):
            return "\n".join(lines[:i]).strip(), "\n".join(lines[i + 1:]).strip()
    return text.strip(), ""


def http_json(url: str, headers: dict, data: dict | None = None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body is not None:
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def secret(src: dict, root: pathlib.Path, what: str) -> str:
    value = qa_config.resolve_secret(src.get("auth", {}), root)
    if not value:
        sys.exit(f"{src.get('auth', {}).get('env_var')} is not set ({what}); see task_source.auth in qa.config.yaml")
    return value


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- adapters

def azure_devops(ref: str, src: dict, root: pathlib.Path) -> dict:
    match = re.search(r"(?:workitems?/(?:edit/)?|AB#|^)(\d+)", ref)
    if not match:
        sys.exit(f"cannot find a work item id in '{ref}'")
    wid = match.group(1)
    org = src["org_url"].rstrip("/")
    az = "az.cmd" if sys.platform == "win32" else "az"
    token = run([az, "account", "get-access-token", "--resource", "499b84ac-1321-427f-aa17-267ca6975798",
                 "--query", "accessToken", "-o", "tsv"]).strip()
    data = http_json(f"{org}/_apis/wit/workitems/{wid}?$expand=relations&api-version=7.1", {"Authorization": f"Bearer {token}"})
    f = data["fields"]
    ac_field = src.get("acceptance_field", "Microsoft.VSTS.Common.AcceptanceCriteria")
    desc_html = f.get("System.Description") or ""
    ac_html = f.get(ac_field) or ""
    repro = f.get("Microsoft.VSTS.TCM.ReproSteps") or ""
    images = re.findall(r'<img[^>]+src="([^"]+)"', desc_html + ac_html + repro)
    description = html_to_text(desc_html)
    if repro:
        description += "\n\nREPRO STEPS:\n" + html_to_text(repro)
    return {
        "id": wid, "url": f"{org}/_workitems/edit/{wid}", "type": f.get("System.WorkItemType"),
        "title": f.get("System.Title"), "state": f.get("System.State"),
        "labels": [t.strip() for t in (f.get("System.Tags") or "").split(";") if t.strip()],
        "area": f.get("System.AreaPath"), "description": description,
        "acceptance_criteria": html_to_text(ac_html), "images": images,
        "links": [f"{r['attributes'].get('name')} {r['url']}" for r in data.get("relations") or []],
        "raw": f,
    }


def jira(ref: str, src: dict, root: pathlib.Path) -> dict:
    match = re.search(r"([A-Z][A-Z0-9]+-\d+)", ref)
    if not match:
        sys.exit(f"cannot find a Jira key in '{ref}'")
    key = match.group(1)
    base = src["base_url"].rstrip("/")
    token = secret(src, root, "Jira API token")
    email = os.environ.get(src["auth"].get("email_env_var", "JIRA_EMAIL"), "")
    cred = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {"Authorization": f"Basic {cred}" if email else f"Bearer {token}", "Accept": "application/json"}
    data = http_json(f"{base}/rest/api/3/issue/{key}?expand=renderedFields", headers)
    f = data["fields"]

    def adf(node) -> str:  # Atlassian document format -> text
        if isinstance(node, str):
            return node
        if not isinstance(node, dict):
            return ""
        if node.get("type") == "text":
            return node.get("text", "")
        inner = "".join(adf(c) for c in node.get("content", []))
        return inner + ("\n" if node.get("type") in ("paragraph", "heading", "listItem", "codeBlock") else "")

    description = adf(f.get("description")) if isinstance(f.get("description"), dict) else (f.get("description") or "")
    ac_field = src.get("acceptance_field")
    ac = adf(f.get(ac_field)) if ac_field and f.get(ac_field) else ""
    if not ac:
        description, ac = split_acceptance(description)
    return {
        "id": key, "url": f"{base}/browse/{key}", "type": (f.get("issuetype") or {}).get("name"),
        "title": f.get("summary"), "state": (f.get("status") or {}).get("name"),
        "labels": f.get("labels") or [], "area": ", ".join(c["name"] for c in f.get("components") or []),
        "description": description.strip(), "acceptance_criteria": ac.strip(),
        "images": [a["content"] for a in f.get("attachment") or [] if str(a.get("mimeType", "")).startswith("image/")],
        "links": [l.get("outwardIssue", l.get("inwardIssue", {})).get("key", "") for l in f.get("issuelinks") or []],
        "raw": f,
    }


def clickup(ref: str, src: dict, root: pathlib.Path) -> dict:
    match = re.search(r"/t/(?:\w+/)?([\w-]+)|^([\w-]+)$", ref)
    if not match:
        sys.exit(f"cannot find a ClickUp task id in '{ref}'")
    tid = match.group(1) or match.group(2)
    token = secret(src, root, "ClickUp API token")
    query = "?include_markdown_description=true"
    if src.get("custom_task_ids"):
        query += f"&custom_task_ids=true&team_id={src['team_id']}"
    d = http_json(f"https://api.clickup.com/api/v2/task/{tid}{query}", {"Authorization": token})
    text = d.get("markdown_description") or d.get("description") or ""
    description, ac = split_acceptance(text)
    return {
        "id": d["id"], "url": d.get("url"), "type": (d.get("custom_item_id") and "custom") or "task",
        "title": d.get("name"), "state": (d.get("status") or {}).get("status"),
        "labels": [t["name"] for t in d.get("tags") or []], "area": (d.get("list") or {}).get("name"),
        "description": description, "acceptance_criteria": ac,
        "images": [a["url"] for a in d.get("attachments") or [] if str(a.get("extension", "")).lower() in ("png", "jpg", "jpeg", "gif", "webp")],
        "links": [l.get("link_id", "") for l in d.get("linked_tasks") or []], "raw": d,
    }


def github(ref: str, src: dict, root: pathlib.Path) -> dict:
    cmd = ["gh", "issue", "view", ref, "--json", "number,title,state,labels,body,url,milestone"]
    if src.get("repo"):
        cmd += ["--repo", src["repo"]]
    d = json.loads(run(cmd))
    description, ac = split_acceptance(d.get("body") or "")
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", d.get("body") or "")
    return {
        "id": str(d["number"]), "url": d["url"], "type": "issue", "title": d["title"], "state": d["state"],
        "labels": [l["name"] for l in d.get("labels") or []], "area": (d.get("milestone") or {}).get("title"),
        "description": description, "acceptance_criteria": ac, "images": images, "links": [], "raw": d,
    }


def linear(ref: str, src: dict, root: pathlib.Path) -> dict:
    match = re.search(r"([A-Z][A-Z0-9]+-\d+)", ref)
    if not match:
        sys.exit(f"cannot find a Linear issue key in '{ref}'")
    token = secret(src, root, "Linear API key")
    query = ("query($id:String!){issue(id:$id){identifier title description url state{name} "
             "labels{nodes{name}} team{name} attachments{nodes{url title}}}}")
    d = http_json("https://api.linear.app/graphql", {"Authorization": token}, {"query": query, "variables": {"id": match.group(1)}})
    i = d["data"]["issue"]
    description, ac = split_acceptance(i.get("description") or "")
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", i.get("description") or "")
    return {
        "id": i["identifier"], "url": i["url"], "type": "issue", "title": i["title"], "state": i["state"]["name"],
        "labels": [l["name"] for l in i["labels"]["nodes"]], "area": i["team"]["name"],
        "description": description, "acceptance_criteria": ac, "images": images,
        "links": [a["url"] for a in i["attachments"]["nodes"]], "raw": i,
    }


def manual(ref: str, src: dict, root: pathlib.Path) -> dict:
    text = sys.stdin.read() if ref == "-" else pathlib.Path(ref).read_text(encoding="utf-8")
    title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.strip()), "manual task")
    description, ac = split_acceptance(text)
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text) + list(src.get("images") or [])
    return {"id": "manual", "url": "", "type": "manual", "title": title, "state": "", "labels": [], "area": "",
            "description": description, "acceptance_criteria": ac, "images": images, "links": [], "raw": {}}


ADAPTERS = {"azure-devops": azure_devops, "jira": jira, "clickup": clickup, "github": github,
            "linear": linear, "manual": manual}


def render(task: dict) -> str:
    out = [f"{k} = {task.get(k)}" for k in ("type", "title", "state", "area")]
    out.append(f"labels = {'; '.join(task.get('labels') or [])}")
    out.append("\nDESCRIPTION:\n" + (task.get("description") or ""))
    out.append("\nACCEPTANCE CRITERIA:\n" + (task.get("acceptance_criteria") or "(none found: derive from the description)"))
    if task.get("images"):
        out.append("\nIMAGES:\n" + "\n".join(task["images"]))
    out.extend(f"LINK {l}" for l in task.get("links") or [])
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ref", help="task id, url, or (manual) a text file / - for stdin")
    parser.add_argument("--save")
    parser.add_argument("--config")
    args = parser.parse_args()

    cfg, root = qa_config.load(pathlib.Path(args.config) if args.config else None)
    src = cfg.get("task_source") or {}
    kind = src.get("type", "manual")
    if kind not in ADAPTERS:
        sys.exit(f"unknown task_source.type '{kind}' (known: {', '.join(ADAPTERS)})")
    task = ADAPTERS[kind](args.ref, src, root)
    if args.save:
        pathlib.Path(args.save).write_text(json.dumps(task, ensure_ascii=False, default=str), encoding="utf-8")
    sys.stdout.buffer.write(render(task).encode("utf-8"))


if __name__ == "__main__":
    main()
