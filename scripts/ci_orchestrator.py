#!/usr/bin/env python3
"""
Plan-driven CI orchestrator.

- Reads expected plan items from issue_backlog.md
- Checks corresponding GitHub issues status
- Runs lightweight local validation
- Emits machine-readable + markdown progress reports

Exit codes:
0 = all plan items completed and checks passed
2 = plan still in progress (not all items closed)
1 = execution error or failed validation
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


BACKLOG_ITEM_PATTERN = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$")
PHASE_PATTERN = re.compile(r"^###\s+Phase\s+(\d+)\s*:\s*(.+?)\s*$", re.IGNORECASE)


@dataclass
class IssueItem:
    raw_title: str
    normalized_title: str
    priority: str


def normalize_title(title: str) -> str:
    title = title.strip().lower()
    title = re.sub(r"\s+", " ", title)
    return title


def detect_priority(title: str) -> str:
    m = re.search(r"\[(p\d+)\]", title.lower())
    return m.group(1).upper() if m else "UNSPECIFIED"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_backlog(backlog_path: Path) -> List[IssueItem]:
    content = read_text(backlog_path)
    items: List[IssueItem] = []

    for line in content.splitlines():
        m = BACKLOG_ITEM_PATTERN.match(line.strip())
        if not m:
            continue
        title = m.group(1).strip()
        if not title:
            continue
        items.append(
            IssueItem(
                raw_title=title,
                normalized_title=normalize_title(title),
                priority=detect_priority(title),
            )
        )

    return items


def parse_plan_phases(plan_path: Path) -> List[Tuple[str, str]]:
    content = read_text(plan_path)
    phases: List[Tuple[str, str]] = []
    for line in content.splitlines():
        m = PHASE_PATTERN.match(line.strip())
        if m:
            phases.append((m.group(1), m.group(2)))
    return phases


def github_request(url: str, token: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_issues(repo: str, token: str) -> List[dict]:
    all_items: List[dict] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repo}/issues"
            f"?state=all&per_page=100&page={page}"
        )
        data = github_request(url, token)
        if not isinstance(data, list) or not data:
            break
        # Pull requests also appear in /issues; exclude them.
        issues_only = [it for it in data if "pull_request" not in it]
        all_items.extend(issues_only)
        if len(data) < 100:
            break
        page += 1
    return all_items


def map_issue_statuses(issues: List[dict]) -> Dict[str, str]:
    status_map: Dict[str, str] = {}
    for issue in issues:
        title = issue.get("title", "")
        if not title:
            continue
        status_map[normalize_title(title)] = issue.get("state", "unknown")
    return status_map


def run_cmd(cmd: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def run_lightweight_checks() -> Dict[str, dict]:
    checks = {}
    targets = ["main.py", "worker.py", "app.py", "dash_app.py"]
    rc, out = run_cmd([sys.executable, "-m", "compileall", *targets])
    checks["python_compileall"] = {"returncode": rc, "output": out}
    return checks


def summarize_completion(
    expected_items: List[IssueItem], issue_status_map: Dict[str, str]
) -> dict:
    missing = []
    open_items = []
    closed_items = []

    for item in expected_items:
        state = issue_status_map.get(item.normalized_title)
        if state is None:
            missing.append(item.raw_title)
        elif state == "closed":
            closed_items.append(item.raw_title)
        else:
            open_items.append(item.raw_title)

    total = len(expected_items)
    done = len(closed_items)
    percent = 0.0 if total == 0 else round((done / total) * 100, 2)

    return {
        "total_items": total,
        "closed_items_count": done,
        "open_items_count": len(open_items),
        "missing_items_count": len(missing),
        "completion_percent": percent,
        "open_items": open_items,
        "missing_items": missing,
        "closed_items": closed_items,
        "is_complete": total > 0 and not open_items and not missing,
    }


def build_markdown_report(
    repo: str,
    phases: List[Tuple[str, str]],
    completion: dict,
    checks: Dict[str, dict],
) -> str:
    lines = []
    lines.append("# Plan Orchestrator Report")
    lines.append("")
    lines.append(f"- Repository: `{repo}`")
    lines.append(f"- Completion: `{completion['completion_percent']}%`")
    lines.append(f"- Total items: `{completion['total_items']}`")
    lines.append(f"- Closed: `{completion['closed_items_count']}`")
    lines.append(f"- Open: `{completion['open_items_count']}`")
    lines.append(f"- Missing issues: `{completion['missing_items_count']}`")
    lines.append(f"- Done: `{completion['is_complete']}`")
    lines.append("")

    if phases:
        lines.append("## Plan Phases")
        for no, name in phases:
            lines.append(f"- Phase {no}: {name}")
        lines.append("")

    lines.append("## CI Checks")
    for name, info in checks.items():
        status = "PASS" if info.get("returncode", 1) == 0 else "FAIL"
        lines.append(f"- {name}: `{status}`")
    lines.append("")

    if completion["open_items"]:
        lines.append("## Open Plan Items")
        for title in completion["open_items"]:
            lines.append(f"- {title}")
        lines.append("")

    if completion["missing_items"]:
        lines.append("## Missing GitHub Issues")
        for title in completion["missing_items"]:
            lines.append(f"- {title}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan-driven CI orchestrator")
    parser.add_argument("--plan-file", default="plan.md")
    parser.add_argument("--backlog-file", default="issue_backlog.md")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""))
    parser.add_argument("--out-json", default="artifacts/plan_status.json")
    parser.add_argument("--out-md", default="artifacts/plan_status.md")
    args = parser.parse_args()

    plan_path = Path(args.plan_file)
    backlog_path = Path(args.backlog_file)

    if not plan_path.exists() or not backlog_path.exists():
        print("plan.md or issue_backlog.md not found.", file=sys.stderr)
        return 1

    expected_items = parse_backlog(backlog_path)
    phases = parse_plan_phases(plan_path)
    checks = run_lightweight_checks()
    checks_failed = any(v.get("returncode", 1) != 0 for v in checks.values())

    if not args.repo or not args.token:
        completion = {
            "total_items": len(expected_items),
            "closed_items_count": 0,
            "open_items_count": len(expected_items),
            "missing_items_count": 0,
            "completion_percent": 0.0,
            "open_items": [i.raw_title for i in expected_items],
            "missing_items": [],
            "closed_items": [],
            "is_complete": False,
            "warning": "Missing repo/token. Issue sync skipped.",
        }
    else:
        try:
            issues = fetch_all_issues(args.repo, args.token)
            status_map = map_issue_statuses(issues)
            completion = summarize_completion(expected_items, status_map)
        except urllib.error.HTTPError as ex:
            print(f"GitHub API request failed: {ex}", file=sys.stderr)
            return 1
        except Exception as ex:  # noqa: BLE001
            print(f"Unhandled error while fetching issues: {ex}", file=sys.stderr)
            return 1

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "repo": args.repo,
        "plan_file": str(plan_path),
        "backlog_file": str(backlog_path),
        "phases": [{"phase": no, "name": name} for no, name in phases],
        "completion": completion,
        "checks": checks,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        build_markdown_report(args.repo or "local", phases, completion, checks),
        encoding="utf-8",
    )

    if checks_failed:
        return 1
    if completion.get("is_complete"):
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
