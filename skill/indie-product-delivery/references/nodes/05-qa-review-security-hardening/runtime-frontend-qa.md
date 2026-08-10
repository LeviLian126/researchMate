# Runtime and Frontend QA

Verify the app actually runs and the frontend works across real devices. Run CP5
through CP8 in order. Every failure here is a runtime defect that users will hit.

## CP5: Start the app

- Start the dev server or run the production build.
- Confirm no startup error: no compile error, no missing dependency, no port conflict,
  no missing environment variable that the app requires.
- If the app cannot start, this is Blocker. Enter CP8 to debug.
- If a required runtime is missing (e.g. database not installed, Redis unavailable), mark CP5
  as NOT_RUN and record exactly what is missing. Do not claim the app works when you could
  not start it.

## CP6: Core user journey E2E

Identify the key user flows from Node01 acceptance criteria or the feature description.
Walk each flow end-to-end.

### For each journey

1. Entry: user arrives at the starting route or screen.
2. Comprehension: the page communicates what to do next.
3. Action: user performs the primary action (click, submit, navigate).
4. Response: the system responds (data loads, state changes, navigation occurs).
5. Feedback: the user sees confirmation or an error message.
6. Navigation: the user can proceed to the next step or return.

### Rules

- Assert on user-observable behavior, not DOM implementation details. Check what the
  user sees and can do, not internal method calls or CSS class names.
- Wait for the page to render before selecting elements. Use condition waits
  (visible text, network idle, element attached), not arbitrary `sleep`.
- Record for each journey: screenshot, console output, network requests.
- Use independent test data. Do not depend on real user data or shared fixtures that
  other tests mutate.
- Each core journey must be verified on at least one mobile resolution and one
  desktop resolution.

### Result

Mark each journey PASS (end-to-end pass) or FAIL (at which step it broke). A failed
journey is at least Major; a failed core journey is Blocker.

## CP7: Multi-resolution frontend visual check

The frontend must render correctly across the full device matrix. A layout that works
on desktop but breaks on mobile is a fail.

### 6-level device matrix

| Level | Width | Representative device | Required |
| --- | --- | --- | --- |
| XS small mobile | 320px | iPhone SE 1st gen, older Android | yes |
| S standard mobile | 390px | iPhone 12-15, Samsung Galaxy S | yes |
| M large mobile | 430px | iPhone Pro Max, Galaxy Note | yes |
| L tablet | 768px | iPad portrait, Android tablet | yes |
| XL small laptop | 1280px | MacBook Air, small laptop | yes |
| XXL desktop | 1920px | standard monitor | yes |

If the project targets a specific device class only (e.g. mobile-only app), you may
adjust the matrix, but state the reason and cover at least the target class at XS,
S, and M.

### Checks for each level

Run every check at each level. Mark PASS or FAIL with a screenshot or description.
At minimum, screenshot XS, S, L, and XXL.

| Category | Check | How to verify |
| --- | --- | --- |
| Layout | elements do not overlap | screenshot and visual check |
| Layout | content does not overflow its container | long text or large data |
| Layout | no unexpected horizontal scrollbar | check at that width |
| Layout | navbar does not wrap or overflow | check at that width |
| Layout | cards, tables, lists are not clipped | check at that width |
| Responsive | breakpoint transitions are smooth, no flicker | resize window across breakpoint |
| Responsive | mobile navigation works (hamburger, collapse, bottom tab) | XS, S, M |
| Responsive | desktop navigation is fully visible | XL, XXL |
| Responsive | grid and flex layouts stack or arrange correctly | compare across levels |
| Touch | tap target is at least 44x44px | XS, S, M |
| Touch | tap targets have enough spacing, no accidental taps | XS, S, M |
| Typography | font size is readable on smallest screen | XS |
| Typography | long text does not overflow or get clipped | all levels |
| Images | images scale to fit, do not overflow | all levels |
| Images | no broken image icon | all levels |
| States | loading state is shown, not blank | trigger a slow request |
| States | empty state is shown, not blank | clear the data |
| States | error state is shown, not blank or crash | trigger an error |
| Navigation | all links and buttons are clickable and go to the right place | click each |
| Navigation | browser back and forward work | navigate then test |
| Forms | validation fires on empty, invalid, boundary input | submit bad data |
| Forms | form does not overflow on narrow screens, fields are usable | XS, S |
| Forms | submission gives feedback (success or error message) | submit valid data |
| Console | no JavaScript errors | devtools console |
| Console | no CSS errors or warnings | devtools console |
| Network | no 4xx or 5xx on core paths | devtools network |
| Network | no failed resource loads (images, CSS, JS) | devtools network |
| Landscape | mobile landscape layout is correct | XS, S, M in landscape |
| Consistency | spacing, alignment, color, and font are consistent | visual check |

### How to run

Prefer Playwright `page.setViewportSize()` to switch viewports programmatically. When
automation is not available, use the browser devtools device toolbar to simulate each
width. Do not rely on physical devices; the goal is consistent viewport coverage, not
hardware testing.

### Failure severity

A layout overlap or overflow on any required level is at least Major. The same issue
on a core path (e.g. the primary action button is overlapped on mobile) is Blocker.
A console error or failed network request on a core path is Blocker.

## CP8: Debug

When CP5, CP6, or CP7 fails, follow this process. Do not make multiple speculative
fixes at once.

1. Record the exact state: route, viewport, device level, data and auth state, error
   message, screenshot.
2. Reproduce narrowly: confirm whether the failure is deterministic, state-dependent,
   environment-dependent, or resolution-specific.
3. Trace the chain: browser, then route, then API, then backend, then state, then
   rendered result. Find where the chain breaks.
4. State one falsifiable hypothesis with the evidence that supports it.
5. Make the smallest fix that tests the hypothesis.
6. Re-run the original verification, then an adjacent regression path, then any other
   resolution that might be affected.

### When to stop and route

If the evidence shows the problem is not local to QA, route to the owning node:

| Evidence says | Route to |
| --- | --- |
| product or acceptance question | Node01 |
| contract or API contradiction | Node02 |
| backend or mock behavior wrong | Node03 |
| frontend implementation defect | Node04 |
| environment or release behavior | Node06 |

### What QA may fix

Narrow, scope-preserving fixes are allowed: an obvious guard or error message in
changed code, a frontend state bug, a CSS layout or responsive breakpoint issue, a
test fixture. Do not change product flow, public API, auth or billing policy, or
perform large refactors. Those go back to their owning node.

After any fix, re-run the checkpoint that failed and record before-and-after evidence.
