# Validation checklist

Before delivery, verify:

- `context/index.html` exists and has one `h1`.
- `context/assets/site.css` and `context/assets/site.js` exist.
- `context/context-state.json` exists and parses.
- Required sections exist: resume, start-here, next-actions, blockers, files, repo-map, handoff, validation, risks, sources.
- No remote assets are loaded through `src` or `href` on `script`, `link`, `img`, `iframe`, `source`, `video`, or `audio`.
- Relative links resolve.
- Source audit lists sources used and missing expected files.
- Decision gates exist and tell the next agent when to stop.
- Context health exists and summarizes confidence, freshness, missing sources, and risks.
- Completion status uses DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT.
- Next actions and blockers are not replaced with vague filler.
- Marketing words do not dominate the page: amazing, unlock, seamless, powerful, beautiful, revolutionary, all-in-one.
- Browser geometry was checked if possible. If not, state that only static validation was run.
