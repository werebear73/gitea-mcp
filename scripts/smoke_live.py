"""Live smoke test for gitea-mcp's issue + repo-metadata tools.

Exercises every implemented tool end-to-end against a real Gitea repository
to catch API-quirk bugs that the mocked unit tests can't.

Usage
-----

Set credentials in your environment:

    $env:GITEA_URL = "https://gitea.example.com"
    $env:GITEA_TOKEN = "your-personal-access-token"

Then run with a test repo (one you don't mind getting a throwaway issue in):

    python scripts/smoke_live.py <owner> <repo>

Or set the repo via env var so it's session-persistent:

    $env:GITEA_TEST_REPO = "owner/repo"
    python scripts/smoke_live.py

The script creates one issue, comments on it, updates the title, closes it,
and re-fetches it to confirm the final state. It does NOT delete the issue
(Gitea doesn't expose a delete endpoint for issues by default).
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

from gitea_mcp.client import GiteaAPIError, GiteaClient
from gitea_mcp.config import Config


def _parse_target(argv: list[str]) -> tuple[str, str]:
    """Pick owner/repo from CLI args or GITEA_TEST_REPO env var."""
    if len(argv) >= 3:
        return argv[1], argv[2]
    env = os.environ.get("GITEA_TEST_REPO", "").strip()
    if env and "/" in env:
        owner, _, repo = env.partition("/")
        if owner and repo:
            return owner, repo
    print(
        "Usage: python scripts/smoke_live.py <owner> <repo>\n"
        "   or set GITEA_TEST_REPO=owner/repo",
        file=sys.stderr,
    )
    sys.exit(2)


async def _run(owner: str, repo: str) -> int:
    config = Config.from_env()
    client = GiteaClient(
        base_url=config.base_url,
        token=config.token,
        timeout=config.timeout,
    )
    # Bind so the tool functions' get_client() returns our client.
    import gitea_mcp.server as server

    server._client = client

    # Import tools AFTER setting the singleton so any registration-time look-ups work.
    from gitea_mcp.tools.issues import (
        add_comment,
        create_issue,
        get_issue,
        list_issues,
        update_issue,
    )
    from gitea_mcp.tools.repos import list_labels, list_milestones, list_repos

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    title = f"gitea-mcp smoke test {timestamp}"
    target = f"{owner}/{repo}"

    print(f"  Target: {target}")
    print(f"  Server: {config.base_url}\n")

    try:
        # ---- Phase 1: repo metadata (read-only) ----
        print(
            f"[Repo metadata 1/3] list_repos(owner={owner!r}) — target should appear ...",
            flush=True,
        )
        repos = await list_repos(owner=owner, limit=50)
        repo_names = [r["name"] for r in repos]
        assert repo in repo_names, (
            f"target {repo!r} not found in {owner}'s repos: {repo_names}"
        )
        print(f"      OK — {owner} has {len(repos)} repo(s) on this page; {repo!r} present\n")

        print(f"[Repo metadata 2/3] list_labels({target!r}) ...", flush=True)
        labels = await list_labels(owner=owner, repo=repo)
        print(f"      OK — {len(labels)} label(s) defined\n")

        print(f"[Repo metadata 3/3] list_milestones({target!r}, state='all') ...", flush=True)
        milestones = await list_milestones(owner=owner, repo=repo, state="all")
        print(f"      OK — {len(milestones)} milestone(s) defined\n")

        # ---- Phase 2: issue workflow (creates + closes one test issue) ----
        print(f"[Issue workflow 1/5] list_issues({target!r}, state='all', limit=5) ...", flush=True)
        existing = await list_issues(owner=owner, repo=repo, state="all", limit=5)
        print(f"      OK — got {len(existing)} issue(s)\n")

        print(f"[Issue workflow 2/5] create_issue({target!r}, title={title!r}) ...", flush=True)
        created = await create_issue(
            owner=owner,
            repo=repo,
            title=title,
            body="Automated smoke test from `scripts/smoke_live.py`. Safe to ignore.",
        )
        issue_number = created["number"]
        print(f"      OK — created #{issue_number}: {created.get('html_url', '(no url)')}\n")

        print(f"[Issue workflow 3/5] add_comment(#{issue_number}, ...) ...", flush=True)
        comment = await add_comment(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            body="smoke test comment",
        )
        print(f"      OK — comment id {comment.get('id')}\n")

        print(
            f"[Issue workflow 4/5] update_issue(#{issue_number}, state='closed', "
            "title=<+ ' (closed)'>) ...",
            flush=True,
        )
        updated = await update_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            title=f"{title} (closed)",
            state="closed",
        )
        assert updated["state"] == "closed", f"expected state=closed, got {updated['state']!r}"
        print(f"      OK — state={updated['state']!r}, title={updated['title']!r}\n")

        print(
            f"[Issue workflow 5/5] get_issue(#{issue_number}) — should show 1 comment ...",
            flush=True,
        )
        final = await get_issue(owner=owner, repo=repo, issue_number=issue_number)
        comments_count = len(final.get("comments_list", []))
        assert final["state"] == "closed", f"final state mismatch: {final['state']!r}"
        assert comments_count >= 1, f"expected >=1 comment, got {comments_count}"
        print(
            f"      OK — state={final['state']!r}, "
            f"comments_list has {comments_count} entry/entries\n"
        )

        print("=" * 60)
        print(f"  All 8 implemented tools passed against {target}.")
        print(
            f"  (3 repo-metadata read-only; 5 issue-workflow — "
            f"test issue closed: #{issue_number})"
        )
        print("=" * 60)
        return 0

    except GiteaAPIError as e:
        print(f"\n  GITEA API ERROR: {e}", file=sys.stderr)
        print(f"  HTTP {e.status_code} on {e.method} {e.url}", file=sys.stderr)
        return 1
    except AssertionError as e:
        print(f"\n  ASSERTION FAILED: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n  UNEXPECTED ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        await client.close()


def main() -> None:
    owner, repo = _parse_target(sys.argv)
    sys.exit(asyncio.run(_run(owner, repo)))


if __name__ == "__main__":
    main()
