# Output contract

## Generated dashboard structure

Default structure inside the target repository:

```text
context/
  index.html
  context-state.json
  assets/
    site.css
    site.js
context.html
```

`context.html` is optional but recommended as a root redirect to `context/index.html`.

## Static constraints

- Use plain HTML, CSS, and vanilla JavaScript.
- Do not load remote CSS, fonts, scripts, images, or analytics.
- All links must be relative or same-page anchors unless they are visible source references intentionally provided by the user.
- The page must remain readable without JavaScript.
- Include exactly one `h1` in `index.html`.
- Use stable section IDs matching the validation script.

## State JSON

`context/context-state.json` must include:

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO-8601 timestamp",
  "repo": "name or path",
  "branch": "branch or unknown",
  "status": "clean | dirty | unknown",
  "confidence": "high | medium | low",
  "objective": "string",
  "next_actions": [],
  "blockers": [],
  "changed_files": [],
  "important_files": [],
  "tests_run": [],
  "tests_not_run": [],
  "risks": [],
  "sources_used": [],
  "sources_missing": []
}
```

## Final response after generation

Report:

- HTML path.
- JSON state path.
- ZIP path if packaged.
- Sources used and missing.
- Validation command and result.
- Limitations such as missing git repo, missing handoff files, or no browser geometry check.
