#!/usr/bin/env python3
"""Tag and publish a GitHub Release for the current (or a given) version.

This is the permanent, self-service release helper. It reads the GitHub token
from a SINGLE, repo-specific environment variable: ``ECHOGIST_GITHUB_TOKEN``.
The name is deliberately namespaced (not the generic ``GITHUB_TOKEN``) so that,
on a machine with several projects, it is unambiguous which token belongs to
which repo and nothing accidentally grabs another project's token.

Set it once in your shell profile (``~/.bashrc``)::

    export ECHOGIST_GITHUB_TOKEN="github_pat_..."   # Contents: Read and write

The human part of a release is the content: bump ``VERSION`` and pyproject's
``version``, write the ``## [X.Y.Z]`` section of ``CHANGELOG.md``, commit it as
``release: vX.Y.Z — <tagline>`` and push ``main``. Everything after that is one
command, with no token in shell history and no secret in the repo:

    python3 scripts/release.py            # tag = v<VERSION file>
    python3 scripts/release.py v1.0.1     # explicit tag

If the tag is not on ``origin`` yet, the script checks that HEAD IS that release
(clean tree, on ``main``, level with ``origin/main``, VERSION == pyproject == tag,
HEAD's subject starts ``release: <tag>``, a CHANGELOG section exists), creates the
annotated tag on HEAD with the subject's ``<tag> — <tagline>`` as its message, and
pushes it. If the tag is already on ``origin`` (re-publishing an older version, or a
retry after a failed publish), it is used as is. The release notes are the matching
CHANGELOG section. Re-running for a tag that already has a release is a no-op
(GitHub's 422 ``already_exists``, reported, exit 0).

The token is read from the environment only and is never printed or committed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_VERSION = _REPO_ROOT / "VERSION"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_ENV_TOKEN = "ECHOGIST_GITHUB_TOKEN"
_BRANCH = "main"


class ReleaseError(Exception):
    """A human-readable, recoverable release failure."""


def _git(*args: str) -> str:
    """Run ``git`` in the repo root (never the caller's cwd) and return its stdout."""
    try:
        return subprocess.run(
            ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise ReleaseError(f"git {' '.join(args)} failed: {exc.stderr.strip()}") from exc
    except OSError as exc:
        raise ReleaseError(f"Could not run git: {exc}.") from exc


def resolve_token() -> str:
    """The token from the repo-specific ``ECHOGIST_GITHUB_TOKEN`` env var.

    Intentionally namespaced (not generic ``GITHUB_TOKEN``) so a multi-project
    machine never publishes with the wrong project's token."""
    token = os.environ.get(_ENV_TOKEN, "").strip()
    if not token:
        raise ReleaseError(
            f"No GitHub token found. Set {_ENV_TOKEN} in your shell profile "
            f'(~/.bashrc): export {_ENV_TOKEN}="github_pat_...". '
            "The token needs 'Contents: Read and write' on this repo."
        )
    return token


def resolve_repo() -> str:
    """``owner/name`` parsed from the ``origin`` remote (https or ssh GitHub URL)."""
    url = _git("remote", "get-url", "origin")
    slug = url
    for prefix in ("https://github.com/", "git@github.com:", "ssh://git@github.com/"):
        if slug.startswith(prefix):
            slug = slug[len(prefix) :]
            break
    slug = slug.removesuffix(".git")
    if slug.count("/") != 1 or not all(slug.split("/")):
        raise ReleaseError(f"Could not parse owner/name from origin URL: {url}.")
    return slug


def _version_file() -> str:
    try:
        return _VERSION.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ReleaseError("The VERSION file is unreadable.") from exc


def resolve_tag(argv: list[str]) -> str:
    """The explicit ``argv[1]`` tag, or ``v<VERSION>``. A bare ``1.2.3`` gets the ``v``."""
    tag = argv[1].strip() if len(argv) > 1 and argv[1].strip() else _version_file()
    return tag if tag.startswith("v") else f"v{tag}"


def changelog_notes(tag: str, repo: str, changelog: Path = _CHANGELOG) -> str:
    """The body of the ``## [X.Y.Z]`` CHANGELOG section matching ``tag`` (the ``v`` and the
    trailing date are ignored), followed by a link to the full changelog.

    A missing or empty section is an error, not a fallback: a release without notes is a
    release whose CHANGELOG step was skipped."""
    version = tag.removeprefix("v")
    try:
        lines = changelog.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReleaseError(f"{changelog.name} is unreadable.") from exc

    body: list[str] = []
    capturing = False
    for line in lines:
        if line.startswith("## "):
            if capturing:  # reached the next version section — stop
                break
            capturing = f"[{version}]" in line
            continue
        if capturing:
            body.append(line)

    text = "\n".join(body).strip()
    if not text:
        raise ReleaseError(f"{changelog.name} has no '## [{version}]' section; write it first.")
    return f"{text}\n\nSee [CHANGELOG.md](https://github.com/{repo}/blob/{_BRANCH}/CHANGELOG.md)."


def tag_on_origin(tag: str) -> bool:
    return bool(_git("ls-remote", "--tags", "origin", f"refs/tags/{tag}"))


def tag_message(tag: str) -> str:
    """The annotation for a new tag, checked against HEAD (see :func:`ensure_tag`).

    Fails unless HEAD is exactly the release commit this tag names: a clean tree, on
    ``main``, level with ``origin/main``, VERSION == pyproject == tag, and a subject of
    ``release: <tag> — <tagline>``. The message is that subject without ``release: ``,
    which is how every tag since v3.0.0 reads."""
    if _git("status", "--porcelain"):
        raise ReleaseError("The working tree is not clean; commit or stash first.")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != _BRANCH:
        raise ReleaseError(f"Releases are cut from {_BRANCH}; HEAD is on {branch}.")
    head = _git("rev-parse", "HEAD")
    remote = _git("ls-remote", "origin", f"refs/heads/{_BRANCH}").split("\t")[0]
    if head != remote:
        raise ReleaseError(
            f"HEAD is not origin/{_BRANCH}; push the release commit first (git push origin "
            f"{_BRANCH}), or pull if origin is ahead."
        )

    version = tag.removeprefix("v")
    try:
        pyproject = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseError("pyproject.toml has no readable [project] version.") from exc
    if not (_version_file() == pyproject == version):
        raise ReleaseError(
            f"Versions disagree: tag {version}, VERSION {_version_file()}, "
            f"pyproject {pyproject}. A new tag is cut only for the version being released."
        )

    subject = _git("log", "-1", "--format=%s")
    if not subject.startswith(f"release: {tag} "):
        raise ReleaseError(
            f"HEAD is not the {tag} release commit (its subject is '{subject}'); expected "
            f"'release: {tag} — <tagline>'."
        )
    return subject.removeprefix("release: ")


def ensure_tag(tag: str) -> None:
    """Make sure ``tag`` is on ``origin`` before anything is published.

    GitHub's create-release endpoint CREATES a missing tag at the default branch head, so
    publishing against a tag that is not there silently invents one. A tag already on
    origin is used as is; otherwise HEAD must be the release (:func:`tag_message`), the
    tag is created on it — or a leftover local tag is reused if it already points there —
    and pushed."""
    if tag_on_origin(tag):
        print(f"{tag} is already on origin; publishing it as is.")
        return
    message = tag_message(tag)
    if _git("tag", "--list", tag):
        annotated = _git("cat-file", "-t", tag) == "tag"
        if not annotated or _git("rev-parse", f"{tag}^{{commit}}") != _git("rev-parse", "HEAD"):
            raise ReleaseError(
                f"A local {tag} exists but is not an annotated tag on HEAD; delete it "
                f"(git tag -d {tag}) and re-run."
            )
    else:
        _git("tag", "-a", tag, "-m", message)
        print(f"Created {tag}: {message}")
    _git("push", "origin", f"refs/tags/{tag}")
    print(f"Pushed {tag} to origin.")


def publish(repo: str, tag: str, notes: str, token: str) -> str:
    """POST the release; return its ``html_url``. A 422 whose error is ``already_exists``
    (a release already exists for the tag) is treated as success — the URL is
    reconstructed from the tag. Any other 422 is a real validation failure."""
    payload = json.dumps(
        {
            "tag_name": tag,
            "name": f"EchoGist {tag}",
            "body": notes,
            "draft": False,
            "prerelease": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "echogist-release",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return str(json.load(resp).get("html_url", ""))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if exc.code == 422 and _already_exists(detail):
            return f"https://github.com/{repo}/releases/tag/{tag} (already published)"
        raise ReleaseError(f"GitHub API {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ReleaseError(f"Network error reaching GitHub: {exc.reason}.") from exc


def _already_exists(detail: str) -> bool:
    try:
        errors = json.loads(detail).get("errors", [])
    except (ValueError, AttributeError):
        return False
    return any(isinstance(e, dict) and e.get("code") == "already_exists" for e in errors)


def main(argv: list[str]) -> int:
    try:
        repo = resolve_repo()
        tag = resolve_tag(argv)
        token = resolve_token()
        notes = changelog_notes(tag, repo)
        ensure_tag(tag)
        print(f"Publishing {repo} release for {tag} ...")
        print(publish(repo, tag, notes, token))
    except ReleaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
