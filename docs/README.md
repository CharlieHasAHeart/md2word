# md2word README

`md2word` is the current application inside this workspace.
It converts Markdown into Word (`.docx`) documents and includes a Markdown cleanup Agent, conversion pipeline, and regression fixtures.

## Main Capabilities

- Convert Markdown into Word with template-based rendering
- Run Markdown cleanup before conversion
- Test cleanup results through a standalone CLI
- Run layered cleanup regressions against fixture cases

## CLI

Convert Markdown to Word:

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run md2word -i input.md -t backend/md2word/templates/reference.docx -o output.docx'
```

Run the Markdown cleanup Agent and write cleaned outputs:

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run md2word-clean -i samples/input.md -o samples/cleaned.md --body-output samples/body.md --meta-output samples/meta.json'
```

Run the cleanup Agent and write a compare directory:

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run md2word-clean -i samples/input.md --compare-output samples/compare-case-01'
```

Run layered cleanup regressions:

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run md2word-clean-regress --compare-output-root /tmp/md2word-regression-run'
```

## Verification

Preferred container command:

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run pytest -q'
```

## Related Docs

- [Markdown Output Spec](markdown-output-spec.md)
