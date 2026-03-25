"""Send a diff to Claude and stream the review."""
from __future__ import annotations
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


def stream_review(
    diff: str,
    model: str = "claude-opus-4-6",
    focus: str | None = None,
    stream: bool = True,
    mode: str = "review",
) -> None:
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
        with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        ) as s:
            for text in s.text_stream:
                print(text, end="", flush=True)
        print()  # final newline
    else:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        print(text)
