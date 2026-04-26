#!/usr/bin/env python3
"""
Sync GitHub issues from issue_backlog.md headings.

- Parses backlog items from lines like: ### 1. [P0][file] Title
- Creates missing issues in the target repository
- Skips titles that already exist (open or closed)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


BACKLOG_ITEM_PATTERN = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$")


@dataclass
class BacklogIssue:
    title: str
    body_lines: List[str]


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_backlog(backlog_path: Path) -> List[BacklogIssue]:
    lines = read_text(backlog_path).splitlines()
    issues: List[BacklogIssue] = []

    current_title = None
    current_body: List[str] = []

    for raw in lines:
        line = raw.rstrip()
        m = BACKLOG_ITEM_PATTERN.match(line.strip())
        if m:
            if current_title:
                issues.append(BacklogIssue(title=current_title, body_lines=current_body))
            current_title = m.group(1).strip()
            current_body = []
            continue

        if current_title is not None:
            # Keep content only inside current issue section.
            if line.startswith("### "):
                continue
            current_body.append(line)

    if current_title:
        issues.append(BacklogIssue(title=current_title, body_lines=current_body))

    return issues


def github_request(url: str, token: str) -> object:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def github_post(url: str, token: str, payload: dict) -> object:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_http_error(ex: urllib.error.HTTPError) -> Tuple[int, str]:
    detail = ""
    try:
        raw = ex.read()
        if raw:
            detail = raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        detail = ""
    return ex.code, detail


def fetch_existing_titles(repo: str, token: str) -> set[str]:
    page = 1
    titles = set()
    while True:
        url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&page={page}"
        data = github_request(url, token)
        if not isinstance(data, list) or not data:
            break
        for it in data:
            if "pull_request" in it:
                continue
            title = it.get("title")
            if title:
                titles.add(normalize_title(title))
        if len(data) < 100:
            break
        page += 1
    return titles


def make_issue_body(item: BacklogIssue) -> str:
    body = "\n".join(item.body_lines).strip()
    header = (
        "Source: `issue_backlog.md`\n\n"
        "This issue is auto-synced from the integration plan backlog.\n"
    )
    if not body:
        return header
    return f"{header}\n---\n\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync plan backlog to GitHub issues")
    parser.add_argument("--backlog-file", default="issue_backlog.md")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out-json", default="artifacts/sync_issues.json")
    args = parser.parse_args()

    backlog_path = Path(args.backlog_file)
    if not backlog_path.exists():
        print("issue_backlog.md not found.", file=sys.stderr)
        return 1

    issues = parse_backlog(backlog_path)
    created = []
    skipped = []
    errors = []

    # Offline dry-run: allow parsing/output without API access.
    if args.dry_run and (not args.repo or not args.token):
        created = [it.title for it in issues]
        result = {
            "repo": args.repo or "local-dry-run",
            "backlog_items": len(issues),
            "created_count": len(created),
            "skipped_count": 0,
            "error_count": 0,
            "created": created,
            "skipped": [],
            "errors": [],
            "warning": "Dry-run without repo/token. API sync skipped.",
        }
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    if not args.repo or not args.token:
        print("Missing repo/token.", file=sys.stderr)
        return 1

    try:
        existing = fetch_existing_titles(args.repo, args.token)
    except urllib.error.HTTPError as ex:
        code, detail = parse_http_error(ex)
        print(f"Failed to fetch existing issues: HTTP {code} {detail}", file=sys.stderr)
        return 1
    except Exception as ex:  # noqa: BLE001
        print(f"Failed to fetch existing issues: {ex}", file=sys.stderr)
        return 1

    for item in issues:
        key = normalize_title(item.title)
        if key in existing:
            skipped.append(item.title)
            continue

        if args.dry_run:
            created.append(item.title)
            continue

        try:
            api = f"https://api.github.com/repos/{args.repo}/issues"
            payload = {"title": item.title, "body": make_issue_body(item)}
            github_post(api, args.token, payload)
            created.append(item.title)
            existing.add(key)
        except urllib.error.HTTPError as ex:
            code, detail = parse_http_error(ex)
            # Handle race condition: another runner may create the same title between list and create.
            if code == 422 and "already exists" in detail.lower():
                skipped.append(item.title)
                existing.add(key)
                continue
            errors.append(f"{item.title}: HTTP {code} {detail}")
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{item.title}: {ex}")

    result = {
        "repo": args.repo,
        "backlog_items": len(issues),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
