import argparse
import os
import subprocess
from dataclasses import dataclass

from config import APP_ENVIRONMENT, BASE_SCAN_PATH
from report import (
    report_blank,
    report_comment,
    report_divider,
    report_error,
    report_exception,
    report_header,
    report_info,
    report_section,
    report_status,
    report_subsection,
    report_warning,
)


@dataclass
class RepoStatus:
    path: str
    name: str
    branch: str
    remote_url: str | None
    has_uncommitted_changes: bool
    needs_push: bool | None
    needs_pull: bool | None
    ahead_count: int | None
    behind_count: int | None
    upstream: str | None
    detail_message: str | None = None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Scan child folders and report local git repository health.")
    parser.add_argument(
        "--base-path",
        default=BASE_SCAN_PATH,
        help="Base path to scan for child folders (default: BASE_SCAN_PATH from .env).",
    )
    return parser.parse_args(argv)


def run_git(repo_path: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )


def get_branch(repo_path: str) -> str:
    branch_cmd = run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch_cmd.returncode != 0:
        return "unknown"
    return branch_cmd.stdout.strip()


def get_remote_url(repo_path: str) -> str | None:
    remote_cmd = run_git(repo_path, ["remote", "get-url", "origin"])
    if remote_cmd.returncode != 0:
        return None
    return remote_cmd.stdout.strip()


def get_upstream(repo_path: str) -> str | None:
    upstream_cmd = run_git(repo_path, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if upstream_cmd.returncode != 0:
        return None
    return upstream_cmd.stdout.strip()


def get_dirty_state(repo_path: str) -> bool:
    status_cmd = run_git(repo_path, ["status", "--porcelain"])
    if status_cmd.returncode != 0:
        raise RuntimeError(status_cmd.stderr.strip() or "Unable to determine working tree status")
    return bool(status_cmd.stdout.strip())


def get_ahead_behind(repo_path: str) -> tuple[int, int]:
    rev_list_cmd = run_git(repo_path, ["rev-list", "--left-right", "--count", "@{upstream}...HEAD"])
    if rev_list_cmd.returncode != 0:
        raise RuntimeError(rev_list_cmd.stderr.strip() or "Unable to determine ahead/behind state")

    output = rev_list_cmd.stdout.strip()
    parts = output.split()
    if len(parts) != 2:
        raise RuntimeError(f"Unexpected rev-list output: '{output}'")

    behind_count = int(parts[0])
    ahead_count = int(parts[1])
    return ahead_count, behind_count


def inspect_repo(repo_path: str) -> RepoStatus:
    branch = get_branch(repo_path)
    remote_url = get_remote_url(repo_path)
    upstream = get_upstream(repo_path)
    has_uncommitted_changes = get_dirty_state(repo_path)

    ahead_count = None
    behind_count = None
    needs_push = None
    needs_pull = None
    detail_message = None

    if upstream:
        try:
            ahead_count, behind_count = get_ahead_behind(repo_path)
            needs_push = ahead_count > 0
            needs_pull = behind_count > 0
        except Exception as exc:
            detail_message = str(exc)
    else:
        detail_message = "No upstream tracking branch configured"

    return RepoStatus(
        path=repo_path,
        name=os.path.basename(repo_path),
        branch=branch,
        remote_url=remote_url,
        has_uncommitted_changes=has_uncommitted_changes,
        needs_push=needs_push,
        needs_pull=needs_pull,
        ahead_count=ahead_count,
        behind_count=behind_count,
        upstream=upstream,
        detail_message=detail_message,
    )


def is_git_repo(path: str) -> bool:
    if not os.path.isdir(path):
        return False

    git_marker = os.path.join(path, ".git")
    if os.path.exists(git_marker):
        return True

    probe = run_git(path, ["rev-parse", "--is-inside-work-tree"])
    return probe.returncode == 0 and probe.stdout.strip().lower() == "true"


def discover_repos(base_path: str) -> list[str]:
    if not os.path.isdir(base_path):
        raise FileNotFoundError(f"Base path does not exist or is not a folder: {base_path}")

    if is_git_repo(base_path):
        return [base_path]

    repo_paths = []
    with os.scandir(base_path) as entries:
        for entry in entries:
            if not entry.is_dir():
                continue

            if is_git_repo(entry.path):
                repo_paths.append(entry.path)

    return sorted(repo_paths, key=lambda path: path.lower())


def report_repo(status: RepoStatus):
    report_section(f"Repository: {status.name}")
    report_subsection(f"Path: {status.path}")
    report_subsection(f"Branch: {status.branch}")
    if status.remote_url:
        report_subsection(f"Remote: {status.remote_url}")
    else:
        report_warning("No 'origin' remote configured")

    if status.has_uncommitted_changes:
        report_warning("Uncommitted changes detected")
    else:
        report_info("No uncommitted changes")

    if status.upstream is None:
        report_warning("No upstream tracking branch set; push/pull checks skipped")
    else:
        report_info(f"Upstream: {status.upstream}")

        if status.needs_push:
            report_warning(f"Committed local changes need push ({status.ahead_count} commit(s) ahead)")
        else:
            report_info("No committed local changes waiting to push")

        if status.needs_pull:
            report_warning(
                f"Remote changes need pull ({status.behind_count} commit(s) behind, as of last local fetch)"
            )
        else:
            report_info("No remote changes waiting to pull (as of last local fetch)")

    if status.detail_message:
        report_comment(f"Detail: {status.detail_message}")


def report_summary(statuses: list[RepoStatus]):
    """Generate actionable todo summary from collected repo statuses."""
    uncommitted = [s for s in statuses if s.has_uncommitted_changes]
    need_push = [s for s in statuses if s.needs_push]
    need_pull = [s for s in statuses if s.needs_pull]

    if not uncommitted and not need_push and not need_pull:
        return

    report_blank()
    report_divider()
    report_section("ACTION REQUIRED SUMMARY")
    report_divider()

    if uncommitted:
        report_section(f"Repos with uncommitted changes ({len(uncommitted)}):")
        for s in uncommitted:
            report_subsection(f"• {s.name} ({s.path})")

    if need_push:
        report_blank()
        report_section(f"Repos that need push ({len(need_push)}):")
        for s in need_push:
            msg = f"• {s.name}"
            if s.ahead_count:
                msg += f" ({s.ahead_count} commit(s) ahead)"
            report_subsection(msg)

    if need_pull:
        report_blank()
        report_section(f"Repos that need pull ({len(need_pull)}):")
        for s in need_pull:
            msg = f"• {s.name}"
            if s.behind_count:
                msg += f" ({s.behind_count} commit(s) behind)"
            report_subsection(msg)

    report_divider()


def main(argv=None):
    args = parse_args(argv)

    report_header(
        app_name="Git Repo Info",
        comp_name=os.environ.get("COMPUTERNAME", "unknown"),
        app_env=APP_ENVIRONMENT,
        user_name=os.environ.get("USERNAME", "unknown"),
    )
    report_section(f"Base path: {args.base_path}")
    report_section("Mode: read-only (no fetch/pull/push)")

    try:
        repo_paths = discover_repos(args.base_path)
        report_section(f"Git repositories found: {len(repo_paths)}")

        if not repo_paths:
            report_warning("No git repositories were found at base path or immediate child folders")
            return 0

        scanned = 0
        repo_errors = 0
        statuses = []
        for repo_path in repo_paths:
            try:
                status = inspect_repo(repo_path)
                report_repo(status)
                statuses.append(status)
                scanned += 1
            except Exception as exc:
                report_error(f"Failed to inspect repository: {repo_path}")
                report_comment(str(exc))
                repo_errors += 1

        report_section(f"Scan complete: {scanned} repository(ies) inspected, {repo_errors} failed")

        # Only show summary for multi-repo scans
        if len(repo_paths) > 1:
            report_summary(statuses)

        return 0 if repo_errors == 0 else 1
    except Exception as exc:
        report_exception("Unhandled error during repository scan", exc)
        return 1
    finally:
        report_status()


if __name__ == "__main__":
    raise SystemExit(main())
