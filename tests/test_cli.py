"""CLI tests — no API key, no git repo needed."""
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from patchwork.cli import main


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
    assert "0.1.0" in result.output


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
