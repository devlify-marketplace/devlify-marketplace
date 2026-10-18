#!/usr/bin/env python3
"""Refresh only the RECENT block from public GitHub data; never generate cards.

No token is used for reads, so private repository data cannot enter the output.
All API reads and validation complete before the README is replaced atomically.
"""
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

USER = os.environ.get("PROFILE_USER", "devlify-marketplace")
README = Path(os.environ.get("README", "README.md"))
START, END = "<!-- RECENT:START -->", "<!-- RECENT:END -->"
NUMBER_PREFIX = re.compile(r"^\s*\d+\s*[-._:)–—]\s*")
BOT_NAMES = {"profile-bot", "github-actions", "github-actions[bot]", "dependabot", "dependabot[bot]", "renovate", "renovate[bot]"}


def public_api(path):
    # Deliberately do not read GITHUB_TOKEN, GH_TOKEN or PROFILE_TOKEN.
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "public-profile-recent-repos"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def clean_text(value):
    value = NUMBER_PREFIX.sub("", " ".join((value or "").split()))
    # Public descriptions remain plain text, not injected HTML or Markdown.
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*\[\]_])", r"\\\1", value).replace("|", "/")


def is_bot_commit(commit):
    account = commit.get("author") or {}
    identity = commit.get("commit", {}).get("author") or {}
    login = account.get("login", "").lower()
    name = identity.get("name", "").lower()
    email = identity.get("email", "").lower()
    return (account.get("type") == "Bot" or login.endswith("[bot]")
            or login in BOT_NAMES or name in BOT_NAMES or name.endswith("[bot]")
            or any(email.startswith(bot + "@") for bot in BOT_NAMES)
            or "[bot]@" in email)


def eligible(repo):
    return (repo.get("private") is False and repo.get("visibility") == "public"
            and not repo.get("fork", True) and not repo.get("archived", True)
            and repo.get("owner", {}).get("login", "").lower() == USER.lower()
            and repo.get("name", "").lower() not in {USER.lower(), ".github"}
            and bool(repo.get("pushed_at")))


def fetch_recent():
    recent = []
    page = 1
    owner = urllib.parse.quote(USER, safe="")
    while len(recent) < 5:
        repos = public_api(f"/users/{owner}/repos?per_page=100&type=owner&sort=pushed&direction=desc&page={page}")
        if not isinstance(repos, list):
            raise ValueError("Invalid repository response")
        for repo in repos:
            if not eligible(repo):
                continue
            name = urllib.parse.quote(repo["name"], safe="")
            branch = urllib.parse.quote(repo["default_branch"], safe="")
            try:
                commits = public_api(f"/repos/{owner}/{name}/commits?sha={branch}&per_page=1")
            except urllib.error.HTTPError as error:
                if error.code == 409:  # Empty repositories have no progress to show.
                    continue
                raise
            if not isinstance(commits, list):
                raise ValueError("Invalid commit response")
            if not commits or is_bot_commit(commits[0]):
                continue
            # Fetch current metadata again before rendering, including visibility.
            current = public_api(f"/repos/{owner}/{name}")
            if not eligible(current):
                continue
            expected_url = f"https://github.com/{USER}/{current['name']}"
            if current.get("html_url", "").lower() != expected_url.lower():
                raise ValueError("Unexpected canonical repository URL")
            recent.append(current)
            if len(recent) == 5:
                break
        if len(repos) < 100:
            break
        page += 1
    if len(recent) != 5:
        raise ValueError("Not enough verified public, human-authored recent repositories")
    return recent


def render(repos):
    lines = []
    for repo in repos:
        title = clean_text(repo["name"])
        description = clean_text(repo.get("description"))
        language = clean_text(repo.get("language"))
        suffix = f" `{language}`" if language else ""
        if description:
            suffix += f": {description}"
        lines.append(f"- [**{title}**]({repo['html_url']}){suffix}")
    return START + "\n" + "\n".join(lines) + "\n" + END


def main():
    try:
        original = README.read_text(encoding="utf-8")
        if original.count(START) != 1 or original.count(END) != 1:
            raise ValueError("Expected one RECENT block")
        begin = original.index(START)
        end = original.index(END)
        if end < begin:
            raise ValueError("Invalid RECENT marker order")
        block = render(fetch_recent())
        updated = original[:begin] + block + original[end + len(END):]
        if updated != original:
            temporary = README.with_name(README.name + ".recent-tmp")
            try:
                temporary.write_text(updated, encoding="utf-8")
                temporary.replace(README)
            finally:
                temporary.unlink(missing_ok=True)
            print("Updated public recent repositories; all other content preserved.")
        else:
            print("No recent repository changes.")
        return 0
    except Exception:
        # Avoid logging API payloads, repository identities or credentials on failure.
        print("Recent refresh failed; last good README and all cards preserved.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
