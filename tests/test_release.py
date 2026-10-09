"""Guards on the release script. It is run once per version, by hand, with a live PAT —
so the failure mode that matters is the one a retry cannot undo: a tag pushed onto the
wrong commit, or a release published against a tag GitHub had to invent."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "echogist_release", Path(__file__).resolve().parent.parent / "scripts" / "release.py"
)
assert _SPEC and _SPEC.loader
release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release)

_HEAD = "a" * 40


class FakeGit:
    """Answers ``_git`` from a table keyed by the argument tuple; records every call."""

    def __init__(self, **overrides: str) -> None:
        self.answers: dict[tuple[str, ...], str] = {
            ("ls-remote", "--tags", "origin", "refs/tags/v2.4.0"): "",
            ("status", "--porcelain"): "",
            ("rev-parse", "--abbrev-ref", "HEAD"): "main",
            ("rev-parse", "HEAD"): _HEAD,
            ("ls-remote", "origin", "refs/heads/main"): f"{_HEAD}\trefs/heads/main",
            ("log", "-1", "--format=%s"): "release: v2.4.0 — a tagline",
            ("tag", "--list", "v2.4.0"): "",
        }
        for key, value in overrides.items():
            self.answers[tuple(key.split(" "))] = value
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        return self.answers.get(args, "")

    @property
    def wrote(self) -> list[tuple[str, ...]]:
        return [c for c in self.calls if c[0] in ("tag", "push") and c[:2] != ("tag", "--list")]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "VERSION").write_text("2.4.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "2.4.0"\n', encoding="utf-8")
    monkeypatch.setattr(release, "_VERSION", tmp_path / "VERSION")
    monkeypatch.setattr(release, "_PYPROJECT", tmp_path / "pyproject.toml")
    return tmp_path


def _use(monkeypatch: pytest.MonkeyPatch, git: FakeGit) -> FakeGit:
    monkeypatch.setattr(release, "_git", git)
    return git


# --------------------------------------------------------------------------- #
# ensure_tag
# --------------------------------------------------------------------------- #
def test_a_ready_head_is_tagged_with_its_subject_and_pushed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git = _use(monkeypatch, FakeGit())

    release.ensure_tag("v2.4.0")

    assert git.wrote == [
        ("tag", "-a", "v2.4.0", "-m", "v2.4.0 — a tagline"),
        ("push", "origin", "refs/tags/v2.4.0"),
    ]


def test_a_tag_already_on_origin_is_published_as_is(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-publishing an old version, or retrying after a failed POST: no checks, no writes."""
    git = _use(
        monkeypatch,
        FakeGit(**{"ls-remote --tags origin refs/tags/v2.4.0": "abc\trefs/tags/v2.4.0"}),
    )

    release.ensure_tag("v2.4.0")

    assert git.wrote == []
    assert ("status", "--porcelain") not in git.calls


@pytest.mark.parametrize(
    ("override", "says"),
    [
        ({"status --porcelain": " M echogist/guard.py"}, "not clean"),
        ({"rev-parse --abbrev-ref HEAD": "feature"}, "cut from main"),
        ({"ls-remote origin refs/heads/main": "b" * 40 + "\trefs/heads/main"}, "not origin/main"),
        ({"log -1 --format=%s": "fix: something else"}, "not the v2.4.0 release commit"),
        # v2.4.0 must not pass as the release commit of v2.4.01.
        ({"log -1 --format=%s": "release: v2.4.01 — x"}, "not the v2.4.0 release commit"),
    ],
)
def test_head_that_is_not_the_release_is_never_tagged(
    repo: Path, monkeypatch: pytest.MonkeyPatch, override: dict[str, str], says: str
) -> None:
    git = _use(monkeypatch, FakeGit(**override))

    with pytest.raises(release.ReleaseError) as exc:
        release.ensure_tag("v2.4.0")

    assert says in str(exc.value)
    assert git.wrote == []


def test_a_typo_tag_is_never_created(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``v2.4.O`` for ``v2.4.0``: GitHub would have invented it at the branch head."""
    git = _use(monkeypatch, FakeGit())

    with pytest.raises(release.ReleaseError) as exc:
        release.ensure_tag("v2.4.O")

    assert "Versions disagree" in str(exc.value)
    assert git.wrote == []


def test_pyproject_out_of_step_stops_the_tag(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "pyproject.toml").write_text('[project]\nversion = "2.3.0"\n', encoding="utf-8")
    git = _use(monkeypatch, FakeGit())

    with pytest.raises(release.ReleaseError, match="Versions disagree"):
        release.ensure_tag("v2.4.0")

    assert git.wrote == []


def test_a_leftover_local_tag_on_head_is_pushed_not_recreated(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that tagged and then failed to push must be re-runnable."""
    git = _use(
        monkeypatch,
        FakeGit(
            **{
                "tag --list v2.4.0": "v2.4.0",
                "cat-file -t v2.4.0": "tag",
                "rev-parse v2.4.0^{commit}": _HEAD,
            }
        ),
    )

    release.ensure_tag("v2.4.0")

    assert git.wrote == [("push", "origin", "refs/tags/v2.4.0")]


@pytest.mark.parametrize(
    ("kind", "commit"),
    [("tag", "c" * 40), ("commit", _HEAD)],  # annotated elsewhere; lightweight on HEAD
)
def test_a_local_tag_that_is_not_the_release_is_never_pushed(
    repo: Path, monkeypatch: pytest.MonkeyPatch, kind: str, commit: str
) -> None:
    git = _use(
        monkeypatch,
        FakeGit(
            **{
                "tag --list v2.4.0": "v2.4.0",
                "cat-file -t v2.4.0": kind,
                "rev-parse v2.4.0^{commit}": commit,
            }
        ),
    )

    with pytest.raises(release.ReleaseError, match="not an annotated tag on HEAD"):
        release.ensure_tag("v2.4.0")

    assert git.wrote == []


# --------------------------------------------------------------------------- #
# _git, changelog_notes, publish
# --------------------------------------------------------------------------- #
def test_git_runs_in_the_repo_root_not_the_callers_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kw)
        return subprocess.CompletedProcess(argv, 0, stdout="out\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)

    assert release._git("status") == "out"
    assert seen["cwd"] == release._REPO_ROOT


def test_notes_are_the_version_section(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n- next\n\n## [2.4.0] — 2026-10-10\n\n- this\n\n"
        "## [2.3.0] — 2026-09-01\n\n- older\n",
        encoding="utf-8",
    )

    notes = release.changelog_notes("v2.4.0", "o/r", changelog)

    assert notes.startswith("- this\n\nSee [CHANGELOG.md](https://github.com/o/r/blob/main/")
    assert "next" not in notes and "older" not in notes


def test_a_missing_changelog_section_stops_the_release(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [2.3.0] — 2026-09-01\n\n- older\n", encoding="utf-8")

    with pytest.raises(release.ReleaseError, match=r"no '## \[2.4.0\]' section"):
        release.changelog_notes("v2.4.0", "o/r", changelog)


def _http_422(monkeypatch: pytest.MonkeyPatch, errors: list[dict[str, str]]) -> None:
    body = json.dumps({"message": "Validation Failed", "errors": errors}).encode()

    def urlopen(req: Any) -> Any:
        raise urllib.error.HTTPError(req.full_url, 422, "Unprocessable", {}, io.BytesIO(body))  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def test_an_existing_release_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    _http_422(monkeypatch, [{"resource": "Release", "code": "already_exists", "field": "tag_name"}])

    assert "already published" in release.publish("o/r", "v2.4.0", "notes", "t")


def test_any_other_validation_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 422 is also GitHub's answer to a bad payload; that must not read as success."""
    _http_422(monkeypatch, [{"resource": "Release", "code": "invalid", "field": "tag_name"}])

    with pytest.raises(release.ReleaseError, match="GitHub API 422"):
        release.publish("o/r", "v2.4.0", "notes", "t")


def test_pyproject_version_is_the_version_file() -> None:
    """VERSION is what release.py tags; pyproject's copy sat at 0.1.0 through nine releases
    because nothing compared them."""
    root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == (root / "VERSION").read_text(encoding="utf-8").strip()
