"""Tests for depfresh."""

from pathlib import Path

import httpx
import pytest
from packaging.requirements import Requirement
from pytest_httpx import HTTPXMock

from depfresh import (
    parse_pyproject,
    get_latest_version,
    version_is_outdated,
    format_spec,
    main,
)


# --- Fixtures ---


@pytest.fixture
def sample_pyproject(tmp_path: Path) -> Path:
    """Create a sample pyproject.toml with various dependency styles."""
    content = """\
[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "requests>=2.28.0",
    "click",
    "pydantic>=2.0.0",
    "numpy==1.24.0",
    "httpx>=0.27,<0.29",
]
"""
    p = tmp_path / "pyproject.toml"
    p.write_text(content)
    return p


@pytest.fixture
def empty_pyproject(tmp_path: Path) -> Path:
    """Create a pyproject.toml with no dependencies."""
    content = """\
[project]
name = "empty"
version = "0.1.0"
dependencies = []
"""
    p = tmp_path / "pyproject.toml"
    p.write_text(content)
    return p


# --- parse_pyproject ---


def test_parse_pyproject(sample_pyproject: Path):
    """Test parsing dependencies from pyproject.toml."""
    deps = parse_pyproject(sample_pyproject)

    assert len(deps) == 5
    names = [dep.name for dep in deps]
    assert names == ["requests", "click", "pydantic", "numpy", "httpx"]


def test_parse_empty_pyproject(empty_pyproject: Path):
    """Test parsing empty dependencies list."""
    deps = parse_pyproject(empty_pyproject)
    assert deps == []


def test_parse_nonexistent_file(tmp_path: Path):
    """Test parsing nonexistent file raises error."""
    with pytest.raises(FileNotFoundError):
        parse_pyproject(tmp_path / "missing.toml")


# --- get_latest_version ---


def test_get_latest_version_success(httpx_mock: HTTPXMock):
    """Test fetching latest version from PyPI."""
    httpx_mock.add_response(
        url="https://pypi.org/pypi/requests/json",
        json={"info": {"version": "2.31.0"}},
    )
    with httpx.Client() as client:
        assert get_latest_version("requests", client) == "2.31.0"


def test_get_latest_version_404(httpx_mock: HTTPXMock):
    """Test handling 404 when package doesn't exist."""
    httpx_mock.add_response(
        url="https://pypi.org/pypi/nonexistent/json",
        status_code=404,
    )
    with httpx.Client() as client:
        assert get_latest_version("nonexistent", client) is None


def test_get_latest_version_invalid_json(httpx_mock: HTTPXMock):
    """Test handling invalid JSON response."""
    httpx_mock.add_response(
        url="https://pypi.org/pypi/bad/json",
        text="not json",
    )
    with httpx.Client() as client:
        assert get_latest_version("bad", client) is None


def test_get_latest_version_missing_version_key(httpx_mock: HTTPXMock):
    """Test handling response missing version field."""
    httpx_mock.add_response(
        url="https://pypi.org/pypi/empty/json",
        json={"info": {}},
    )
    with httpx.Client() as client:
        assert get_latest_version("empty", client) is None


# --- version_is_outdated ---


def test_version_outdated_greater_or_equal():
    """Test detecting outdated >= specifier — >=2.28 allows 2.31."""
    req = Requirement("requests>=2.28.0")
    assert version_is_outdated(req, "2.31.0") is False  # 2.31 >= 2.28, so OK
    assert version_is_outdated(req, "2.28.0") is False


def test_version_outdated_pinned():
    """Test detecting outdated pinned version."""
    req = Requirement("requests==2.28.0")
    assert version_is_outdated(req, "2.31.0") is True  # pinned, newer exists
    assert version_is_outdated(req, "2.28.0") is False


def test_version_outdated_upper_bound():
    """Test detecting outdated when latest is beyond upper bound."""
    req = Requirement("requests>=2.28.0,<2.30.0")
    assert version_is_outdated(req, "2.31.0") is True  # beyond <2.30
    assert version_is_outdated(req, "2.29.0") is False


def test_version_outdated_exact():
    """Test detecting outdated == specifier."""
    req = Requirement("numpy==1.24.0")
    assert version_is_outdated(req, "1.25.0") is True
    assert version_is_outdated(req, "1.24.0") is False


def test_version_outdated_range():
    """Test detecting outdated range specifier."""
    req = Requirement("httpx>=0.27,<0.29")
    assert version_is_outdated(req, "0.27.0") is False
    assert version_is_outdated(req, "0.28.5") is False
    assert version_is_outdated(req, "0.29.0") is True


def test_version_outdated_no_specifier():
    """Test that no specifier means never outdated."""
    req = Requirement("click")
    assert version_is_outdated(req, "99.0.0") is False


def test_version_outdated_invalid_version():
    """Test handling invalid version string."""
    req = Requirement("requests>=1.0")
    assert version_is_outdated(req, "not-a-version") is False


# --- format_spec ---


def test_format_spec_no_specifier():
    """Test formatting requirement with no specifier."""
    req = Requirement("click")
    assert format_spec(req) == "(any)"


def test_format_spec_with_specifier():
    """Test formatting requirement with specifier."""
    req = Requirement("requests>=2.28.0")
    assert "2.28.0" in format_spec(req)


def test_format_spec_range():
    """Test formatting requirement with range specifier."""
    req = Requirement("httpx>=0.27,<0.29")
    spec = format_spec(req)
    assert "0.27" in spec
    assert "0.29" in spec


# --- main ---


def test_main_no_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """Test main exits with error when pyproject.toml missing."""
    monkeypatch.chdir(tmp_path)
    assert main() == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_main_no_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """Test main handles empty dependencies list."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1"\ndependencies = []\n'
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "No dependencies" in captured.out


def test_main_all_up_to_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture,
):
    """Test main when all dependencies are up to date."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.1"\ndependencies = ["requests>=2.28.0", "click"]\n'
    )

    httpx_mock.add_response(
        url="https://pypi.org/pypi/requests/json",
        json={"info": {"version": "2.28.0"}},
    )
    httpx_mock.add_response(
        url="https://pypi.org/pypi/click/json",
        json={"info": {"version": "8.1.7"}},
    )

    assert main() == 0
    captured = capsys.readouterr()
    assert "All dependencies are up to date" in captured.out


def test_main_outdated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture,
):
    """Test main detects outdated dependencies."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.1"\ndependencies = ["requests>=2.28.0,<2.30.0"]\n'
    )

    httpx_mock.add_response(
        url="https://pypi.org/pypi/requests/json",
        json={"info": {"version": "2.31.0"}},
    )

    assert main() == 1
    captured = capsys.readouterr()
    assert "2.31.0" in captured.out
    assert "outdated" in captured.out.lower()


def test_main_invalid_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """Test main handles malformed TOML gracefully."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project\nname = broken\n'
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "Error parsing" in captured.err


def test_main_fetch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture,
):
    """Test main handles PyPI fetch failures gracefully."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.1"\ndependencies = ["nonexistent-pkg"]\n'
    )

    httpx_mock.add_response(
        url="https://pypi.org/pypi/nonexistent-pkg/json",
        status_code=404,
    )

    # Should not crash, just show warning
    assert main() == 0
    captured = capsys.readouterr()
    assert "could not fetch" in captured.out


def test_main_mixed_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture,
):
    """Test main with mix of up-to-date and outdated dependencies."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.1"\ndependencies = ["requests>=2.28.0,<2.30.0", "click"]\n'
    )

    httpx_mock.add_response(
        url="https://pypi.org/pypi/requests/json",
        json={"info": {"version": "2.31.0"}},
    )
    httpx_mock.add_response(
        url="https://pypi.org/pypi/click/json",
        json={"info": {"version": "8.1.7"}},
    )

    assert main() == 1
    captured = capsys.readouterr()
    assert "up to date" in captured.out
    assert "outdated" in captured.out.lower()


def test_python_m_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that python -m depfresh works."""
    import subprocess
    import sys

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.1"\ndependencies = []\n'
    )

    result = subprocess.run(
        [sys.executable, "-m", "depfresh"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "No dependencies" in result.stdout

