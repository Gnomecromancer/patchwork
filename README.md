# patchwork

AI code review for your git diffs. Powered by Claude.

```
pip install patchwork-review
export ANTHROPIC_API_KEY=sk-ant-...
patchwork review
```

## Usage

```
# Review staged + unstaged changes
patchwork review

# Review only staged changes
patchwork review --staged

# Review last 3 commits
patchwork review --since HEAD~3

# Review diff vs main branch
patchwork review --since main

# Review a specific file
patchwork review -f src/auth.py

# Focus the review
patchwork review --focus "security vulnerabilities only"
patchwork review --focus "look for N+1 queries"

# Explain a file
patchwork explain src/utils.py
```

## Output

Structured Markdown:

```markdown
## Summary
...

## Issues
...

## Suggestions
...

## Verdict
**Approve** / **Request Changes** / **Needs Discussion**
```

## Model

Defaults to `claude-opus-4-6`. Override with `--model`:

```
patchwork review --model claude-sonnet-4-6
```

## License

MIT
