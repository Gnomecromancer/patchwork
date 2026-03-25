"""Send a diff to Claude and stream the review."""
from __future__ import annotations
import html
import os
import sys

import anthropic

_REVIEW_SYSTEM = """\
You are a senior software engineer doing a thorough code review.
Review the diff below and provide structured feedback in Markdown.

Structure your response as:

## Summary
One paragraph describing what the change does.

## Issues
List any bugs, logic errors, security vulnerabilities, or correctness problems.
Be specific: quote the relevant code, explain why it's a problem, and suggest a fix.
If there are no issues, write "None found."

## Suggestions
Style improvements, better abstractions, performance wins, missing error handling.
These are non-blocking but worth considering.

## Verdict
One of: **Approve** / **Request Changes** / **Needs Discussion**
One sentence explaining the verdict.

Be direct. Don't praise boilerplate. Don't pad the review.
If the diff is trivial and clean, say so briefly."""


_EXPLAIN_SYSTEM = """\
You are a senior software engineer explaining code to a colleague.
Be clear, direct, and accurate. Use Markdown. Include:
- What the code does (purpose)
- How it works (key logic)
- Design choices and tradeoffs
- Any gotchas or non-obvious behavior

Don't restate obvious things. Focus on what's actually interesting or tricky."""


def render_html(content: str, meta: dict) -> str:
    """Render a review string as a self-contained HTML file with a dark theme.

    Args:
        content: The plain-text / Markdown review output.
        meta:    Dict with keys like ``model``, ``path``, ``date``.

    Returns:
        A complete HTML document string.
    """
    escaped = html.escape(content)

    meta_rows = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
        for k, v in meta.items()
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>patchwork review</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e1e1e;
    color: #d4d4d4;
    font-family: 'Consolas', 'Menlo', 'Monaco', 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.6;
    padding: 2rem;
  }}
  h1 {{
    color: #9cdcfe;
    font-size: 1.4rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid #333;
    padding-bottom: 0.5rem;
  }}
  table.meta {{
    border-collapse: collapse;
    margin-bottom: 1.5rem;
    font-size: 0.85rem;
  }}
  table.meta th {{
    color: #808080;
    text-align: left;
    padding: 0.15rem 1rem 0.15rem 0;
    white-space: nowrap;
    font-weight: normal;
  }}
  table.meta td {{
    color: #ce9178;
  }}
  pre {{
    background: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 1.25rem 1.5rem;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }}
</style>
</head>
<body>
<h1>patchwork review</h1>
<table class="meta">
{meta_rows}
</table>
<pre>{escaped}</pre>
</body>
</html>
"""


def stream_review(
    diff: str,
    model: str = "claude-opus-4-6",
    focus: str | None = None,
    stream: bool = True,
    mode: str = "review",
) -> str:
    """Stream (or collect) a review from Claude and return the full text."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY not set.\n"
            "Get a key at https://console.anthropic.com/ and set:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    system = _EXPLAIN_SYSTEM if mode == "explain" else _REVIEW_SYSTEM

    user_content = diff
    if focus:
        user_content = f"Focus: {focus}\n\n{diff}"

    if stream:
        chunks: list[str] = []
        with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        ) as s:
            for text in s.text_stream:
                print(text, end="", flush=True)
                chunks.append(text)
        print()  # final newline
        return "".join(chunks)
    else:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        print(text)
        return text
