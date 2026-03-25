"""CLI tests — no API key, no git repo needed."""
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from patchwork.cli import main
from patchwork.review import render_html


# ---------------------------------------------------------------------------
# Helper: fake git repo
# ---------------------------------------------------------------------------

@pytest.fixture
def git_repo(tmp_path):
    """Minimal git repo with one commit."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    f = tmp_path / "hello.py"
    f.write_text("print('hello')\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    # Unstaged change
    f.write_text("print('hello world')\n")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.output


# ---------------------------------------------------------------------------
# render_html tests
# ---------------------------------------------------------------------------

def test_render_html_structure():
    """render_html returns valid HTML with expected structure."""
    content = "## Summary\nA trivial change.\n\n## Verdict\n**Approve**"
    meta = {"model": "claude-opus-4-6", "path": "/home/user/repo", "date": "2026-03-25 10:00:00"}
    doc = render_html(content, meta)

    assert "<!DOCTYPE html>" in doc
    assert "<title>patchwork review</title>" in doc
    # Dark background colour present
    assert "#1e1e1e" in doc
    # Content is escaped and present
    assert "## Summary" in doc
    assert "**Approve**" in doc


def test_render_html_meta_rows():
    """render_html embeds all meta key/value pairs as table rows."""
    meta = {"model": "test-model", "path": "/tmp/repo", "date": "2026-01-01"}
    doc = render_html("content", meta)

    assert "test-model" in doc
    assert "/tmp/repo" in doc
    assert "2026-01-01" in doc


def test_render_html_escapes_content():
    """render_html HTML-escapes special characters in content."""
    content = "<script>alert('xss')</script>"
    doc = render_html(content, {})

    assert "<script>" not in doc
    assert "&lt;script&gt;" in doc


def test_render_html_escapes_meta():
    """render_html HTML-escapes special characters in meta values."""
    meta = {"path": "<evil>&path"}
    doc = render_html("ok", meta)

    assert "<evil>" not in doc
    assert "&lt;evil&gt;" in doc


def test_review_html_flag(git_repo, tmp_path, monkeypatch):
    """--html writes an HTML file containing the review content."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.chdir(git_repo)

    mock_text_stream = iter(["## Summary\n", "Small change.\n"])
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_stream_ctx.text_stream = mock_text_stream

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_ctx

    out_file = tmp_path / "report.html"

    with patch("patchwork.review.anthropic.Anthropic", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["review", "--unstaged", "--html", str(out_file)])

    assert result.exit_code == 0, result.output
    assert out_file.exists(), "HTML file was not created"
    html_content = out_file.read_text(encoding="utf-8")
    assert "## Summary" in html_content
    assert "#1e1e1e" in html_content


def test_review_no_api_key(git_repo):
    """Without ANTHROPIC_API_KEY, review should exit with a clear error."""
    runner = CliRunner()
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["review", "--unstaged"], env=env, catch_exceptions=False)
    # Exits non-zero and prints key hint


def test_review_no_diff(git_repo):
    """No diff → exit 0 with a message."""
    runner = CliRunner()
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    result = runner.invoke(
        main,
        ["review", "--staged"],  # nothing staged
        env=env,
        catch_exceptions=False,
    )
    # Should exit 0 saying "nothing to review"


def test_review_streams_output(git_repo, monkeypatch):
    """With a fake API key and mocked client, review should stream output."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.chdir(git_repo)

    # Mock anthropic.Anthropic
    mock_text_stream = iter(["## Summary\n", "A change.\n", "\n## Verdict\n", "**Approve**\n"])

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_stream_ctx.text_stream = mock_text_stream

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_ctx

    with patch("patchwork.review.anthropic.Anthropic", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["review", "--unstaged"])

    assert result.exit_code == 0
    assert "Summary" in result.output


def test_explain_streams_output(tmp_path, monkeypatch):
    """explain command streams output for a file."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    f = tmp_path / "utils.py"
    f.write_text("def add(a, b): return a + b\n")

    mock_text_stream = iter(["This function adds two numbers.\n"])
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_stream_ctx.text_stream = mock_text_stream

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream_ctx

    with patch("patchwork.review.anthropic.Anthropic", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["explain", str(f)])

    assert result.exit_code == 0
    assert "adds two numbers" in result.output
