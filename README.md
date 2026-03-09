# git_repo_info

Scan either a single Git repo path or immediate child folders under a base path and report Git repository health in read-only mode.

## What it reports

For each discovered Git repo, the tool reports:

1. Whether there are uncommitted local changes.
2. Whether local commits are ahead of upstream (need push).
3. Whether upstream appears ahead of local (need pull).

The pull status is based on existing local tracking refs only (as of last local fetch).

## Safety (do no harm)

This tool does not run `git fetch`, `git pull`, `git push`, `git commit`, or any other mutating Git command.
It only reads local repository state and reports findings.

## Configuration

Create a `.env` file in the project root:

```env
APP_ENVIRONMENT=local
DATA_DIR=./data
BASE_SCAN_PATH=c:\\git
```

- `BASE_SCAN_PATH` is the default path to scan (single repo or parent folder).
- You can override base path from CLI with `--base-path`.

## Install

```bash
poetry install
```

## Run

Using `.env` base path:

```bash
poetry run git-repo-info
```

Override base path:

```bash
poetry run git-repo-info --base-path c:\\git
```

Run against a single repo directly:

```bash
poetry run git-repo-info --base-path C:\\Users\\jmedlin\\Documents\\Github\\Goal_Tracker
```
