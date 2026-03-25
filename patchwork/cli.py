"""
patchwork CLI — AI code review for git diffs.

    patchwork review                     # review staged changes
    patchwork review --unstaged          # review unstaged changes
    patchwork review --since HEAD~3      # review last 3 commits
    patchwork review --file path/to/f   # review specific file diff
    patchwork review --pr 42            # review a PR (requires gh CLI)
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

import click

from . import __version__
from .review import stream_review

_DEFAULT_MODEL = "claude-opus-4-6"


def _git(*args) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise click.ClickException(f"git error: {result.stderr.strip()}")
    return result.stdout


def _get_diff(
    staged: bool,
    unstaged: bool,
    since: str | None,
    file: str | None,
) -> str:
    file_args = [file] if file else []

    if since:
        diff = _git("diff", since, "--", *file_args)
    elif staged:
        diff = _git("diff", "--staged", "--", *file_args)
    elif unstaged:
        diff = _git("diff", "--", *file_args)
    else:
        # Default: staged + unstaged together
        staged_diff = _git("diff", "--staged", "--", *file_args)
        unstaged_diff = _git("diff", "--", *file_args)
        diff = staged_diff + unstaged_diff

    return diff.strip()


@click.group()
@click.version_option(__version__)
def main():
    """patchwork — AI code review for your git diffs."""


@main.command()
@click.option("--staged", "-s", is_flag=True, help="Review only staged changes (default: staged + unstaged).")
@click.option("--unstaged", "-u", is_flag=True, help="Review only unstaged changes.")
@click.option("--since", metavar="REF", default=None, help="Review diff since a commit/ref (e.g. HEAD~3, main).")
@click.option("--file", "-f", "filepath", default=None, metavar="PATH", help="Limit diff to a specific file.")
@click.option("--model", "-m", default=_DEFAULT_MODEL, show_default=True, help="Claude model to use.")
@click.option("--focus", default=None, metavar="TEXT",
              help="Optional focus instructions (e.g. 'security only' or 'look for N+1 queries').")
@click.option("--no-stream", is_flag=True, help="Wait for full response before printing.")
def review(
    staged: bool,
    unstaged: bool,
    since: str | None,
    filepath: str | None,
    model: str,
    focus: str | None,
    no_stream: bool,
):
    """
    Review your git diff with Claude.

    \b
    Examples:
        patchwork review                     # staged + unstaged
        patchwork review --staged            # only staged
        patchwork review --since HEAD~3      # last 3 commits
        patchwork review --since main        # diff vs main branch
        patchwork review -f src/auth.py      # single file
        patchwork review --focus "security"
    """
    try:
        diff = _get_diff(staged, unstaged, since, filepath)
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e))

    if not diff:
        click.echo("No diff found. Nothing to review.", err=True)
        sys.exit(0)

    lines = diff.count("\n")
    click.echo(f"reviewing {lines} line diff with {model} …\n", err=True)

    try:
        stream_review(diff, model=model, focus=focus, stream=not no_stream)
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--model", "-m", default=_DEFAULT_MODEL, show_default=True)
@click.option("--focus", default=None, metavar="TEXT")
@click.option("--no-stream", is_flag=True)
def explain(path: str, model: str, focus: str | None, no_stream: bool):
    """
    Explain a file or snippet.

    \b
    Examples:
        patchwork explain src/auth.py
        patchwork explain src/utils.py --focus "explain the caching logic"
    """
    content = Path(path).read_text(encoding="utf-8", errors="replace")
    suffix = Path(path).suffix or ".txt"
    diff = f"```{suffix.lstrip('.')}\n{content}\n```"

    focus_text = focus or f"explain this code clearly, including purpose, design choices, and any gotchas"
    click.echo(f"explaining {path} …\n", err=True)

    try:
        stream_review(diff, model=model, focus=focus_text, stream=not no_stream, mode="explain")
    except Exception as e:
        raise click.ClickException(str(e))
