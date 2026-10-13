# Parexa conversation studio — design QA

final result: passed

## Reference and captures

- Selected visual: displayed option 2, `exec-afb54ede-9e43-40b5-9a78-a2ca591d5f77.png` in the current chat's generated-images directory.
- Reference pixels and desktop CSS viewport: 1487 × 1058. Implementation capture: 1487 × 1058, device scale factor 1.
- Compared both images together in `artifacts/studio-comparison.jpg`, with typography and composer detail comparisons. Captures include `studio-desktop-chat.jpg`, `studio-mobile.jpg`, `studio-mobile-chat.jpg`, `studio-dark.jpg`, and `studio-settings.jpg`.
- Browser preview uses the repository's fixture API on port 5001. Its model names, conversation history, replies, and upload results are fixtures, not live inference.

## Findings and repairs

- Resolved P1: inherited tablet rules turned the sidebar into a horizontal header and hid navigation. The studio layer explicitly retains the vertical sidebar until the mobile drawer breakpoint.
- Resolved P2: hardcoded white history labels lost contrast on light surfaces; inherited settings styles retained purple accents. Labels and supporting controls now use studio tokens.
- Resolved P2: inherited reasoning-control widths forced a third composer row on mobile. Compact intrinsic widths keep the composer to two rows at 390 × 844.
- Resolved P2: assistant wrapper sizing created horizontal scrolling. Flexible message content now fits its parent, and long code/table content scrolls inside the content area.
- Resolved P2: settings/activity drawers did not move or contain keyboard focus. Opening focuses the first control, Tab wraps within overlays, and closing restores reachable focus.
- Resolved functional issue: an already selected conversation could not be reopened after reload left an empty chat. Clicking that row now fetches history when the log is empty.

## Required fidelity surfaces

- Typography: existing Manrope body and display typography retained; 18px desktop conversation text, 15px mobile text, and a 30px desktop title reproduce the readable editorial hierarchy. Sidebar/control labels stay compact.
- Spacing/layout: flat application surface, slim sidebar, centered conversation, small user bubble, unboxed assistant text, and persistent bottom composer. Research desk starts closed. At 390 × 844, navigation becomes a drawer and the research desk an overlay; composer remains within the viewport.
- Colors/tokens: white and light neutral surfaces, graphite text, restrained cyan actions, and corresponding dark tokens. No decorative hero or gradient background remains visible.
- Assets: original Parexa vector mark retained; Feather MIT-licensed source icons vendored locally. No generated mockup is embedded as the interface.
- Copy/content: actual conversation title and selected provider/model drive labels. Four starters invoke existing handlers. Sources distinguish next-request attachments from previous-request references; notes explicitly remain browser-local.

## Accepted differences from the mockup

- The fixture contains two history entries rather than the mockup's invented full history. Production renders only actual API results; date groupings were not invented.
- Model controls report the discovered fixture model rather than showing the mockup's disconnected state. Disconnected selection was separately checked.
- Standard and Genesis are directly selectable beside the composer. Existing sidebar visibility and overview controls remain available.
- Unsupported feedback buttons, user-avatar chrome, and an unexplained overflow menu were not added. Response text remains API content rather than hardcoded mockup prose.
- Native Markdown list markers retain the existing renderer rather than introducing special markup for a single example response.

## Validation

- Passed: 7 Observatory structural checks and 7 model-gateway checks; syntax checks for all four application scripts; Python compilation of the updated smoke script; `git diff --check`.
- Exercised in the Codex browser: text reply, attachment upload and attached reply, citation opening Sources, model deselection/reselection, Standard/Genesis and browsing toggles, history loading/reopening, new chat, notes persistence across reload, settings, activity, dark/light appearance, keyboard focus wrapping, Escape dismissal, mobile navigation and research overlays.
- Desktop and mobile DOM measurements found no page/chat horizontal overflow; composer bottom remained within the viewport.
- No console errors originating from port 5001 were observed. An earlier port-5000 static preview logged an expected unavailable-API error before fixture testing.
- Reduced-motion rules were statically checked; an operating-system reduced-motion preference was not emulated.
- The standalone Playwright smoke runner was updated but not executed; its fixture handler was used for browser testing through Codex's browser tools.
- Real Flask startup, inference, OCR, Qdrant and document RAG remain unverified because backend dependencies are absent.

## Completion

No outstanding P0/P1/P2 visual findings. Keep source/API contracts and local-only delivery intact. Future polish can refine the generic Markdown list appearance without changing application behavior.

## Browser annotation follow-up

The selected brand label now reads only Parexa, and the page title no longer includes Observatory. The annotated history area now supports local chat folders: create, rename, collapse/expand, move to a folder or Unfiled, and remove a folder without deleting chats. Folder names, membership, and collapsed state survive reload through `parexa.chat-folders.v1`. This is browser-local organization; backend history APIs remain unchanged.

Browser checks passed for creation, moving a fixture conversation, collapsed-state persistence after reload, prefilled rename, renamed membership, and removal returning both fixture conversations to the history list. The final screenshot is `artifacts/parexa-chat-folders.jpg`. Structural tests, JavaScript syntax, smoke-script compilation, and diff whitespace checks passed. The standalone smoke runner includes regression coverage but was not executed.

## Nested folders and expressive panel follow-up

The next annotations and explicit visual-direction choice supersede the earlier flat panel styling. Each folder now has a New subfolder action. Full paths identify nested move targets and action labels. Existing v1 folder data gains an additive nullable parentId without losing names, collapse state, or chat assignments. Parent removal promotes its child folders and retains their chats; direct chats return to Unfiled. Folder counts include descendant chats. Deep indentation is capped to keep actions reachable.

The requested expressive Parexa styling uses a cyan header band and original logo, tinted canvas, solid cyan user messages, white/dark answer surfaces with an accent edge, and a more prominent composer. Before/after comparison: `artifacts/parexa-expressive-comparison.jpg` (two 884 × 750 captures). All application text, backend contracts, and existing controls remain functional. The larger answer padding is an intentional response to the request for bolder styling.

Verified through the browser: three nested levels, full-path chat movement, collapse and membership across reload, aggregate counts, light/dark appearance, and narrow mobile layout with no page/chat horizontal overflow and a visible composer. The browser zoom caused the mobile 390 × 844 physical override to correspond to a measured 325 × 703 CSS viewport; no claim of an exact 390px CSS capture is made. Final captures: `parexa-expressive-nested.jpg`, `parexa-expressive-dark.jpg`, and `parexa-expressive-mobile.jpg`.

Passed `node tests/chat_folders_test.cjs` for legacy migration, parent-first ordering, nested full paths, cycle/self-parent/orphan recovery, malformed storage, and preserving descendants on parent removal. The 7 UI structural checks, script syntax check, and diff whitespace check also passed. Preview remains a fixture API, now launched through a hidden local helper so it can remain available between chat turns. No outstanding P0/P1/P2 findings in the annotated changes.

## Custom scroll and cursor follow-up

Native scrollbar colors and rounded fallback thumbs now match the cyan palette in light/dark modes. Locally served Feather-derived SVG cursors provide outlined default and filled action variants on fine-pointer devices; text inputs retain the text cursor, and disabled controls retain not-allowed. Touch devices are not given custom cursor rules; forced-colors mode uses native rendering.

Browser computed styles verified both SVG cursor URLs, a text cursor in the composer, and cyan scrollbar colors. Native scrolling changed chat scrollTop from 0 to approximately 166.7 without an interception handler. The action asset returned HTTP 200. Screenshot: `artifacts/parexa-custom-scroll.jpg`; native cursor images are not captured in the page screenshot. The 7 UI structural checks and diff whitespace check passed. No new JavaScript or dependencies were added.

## Iris BTC reference and complete interaction styling

The supplied 1904 × 137 Iris BTC reference and local `bitcoin-iris/terminal/src/app/globals.css` ground this iteration. The new terminal layer adapts charcoal surface ramps, monospaced navigation/headings, thin borders, and amber active states to Parexa's existing conversation layout. Parexa's logo, cyan secondary accents, and readable conversation body typography remain. Iris market tabs, prices, and graph imagery are not added to a chat product.

Required surfaces: chrome typography uses existing system monospace fonts; controls/panels use compact angular geometry; colors map to explicit light/dark terminal tokens; original logo and licensed local cursor/icon assets remain sharp; titles, model state, and application actions continue to reflect actual UI state. Hover, pressed, selected, focus, text caret, selection, disabled, and scrollbar treatments are coordinated across the workspace.

Added a native modal command surface (Ctrl/Cmd+K), searchable commands, arrow navigation, Enter execution, empty results, and Escape dismissal with focus return. Actions reuse existing handlers. Tested Notes and Choose model commands with focus landing on the scratchpad and model select respectively; Escape from commands leaves an underlying inspector open. Existing `/` composer shortcut is blocked while modal commands are active.

Fine-pointer cursor mappings include default, action hand, text, disabled, busy, and range/move states; text and action SVG URLs were confirmed through computed styles. Native/forced-colors and touch fallbacks remain. No mouse-tracking loop is introduced. Busy and disabled cursor declarations were statically reviewed rather than exercised against a delayed inference backend.

Visual comparison: `parexa-iris-header-comparison.jpg` pairs the supplied header with a normalized implementation header. The screenshot canvas was 2560 × 1421 while the app occupied a measured 1920 × 1066 CSS region. The handoff copy `parexa-iris-terminal-normalized.jpg` crops away the extra capture area at the app bounds without scaling UI pixels. This is an adaptation of the reference's visual language rather than a duplicate of its two-row market header. Narrow testing measured a 520 × 1125 CSS viewport due browser zoom: no horizontal overflow, composer remained visible, and the command dialog fit within the viewport. Temporary viewport overrides were reset.

The fixture preview now preserves static version query parameters so browser checks exercise current assets. Passed UI structural checks, folder regressions, syntax checks, smoke-script compilation, and diff whitespace checks. The standalone smoke runner remains unexecuted; interactive command checks used Codex's browser. Final captures include `parexa-iris-terminal.jpg` and `parexa-terminal-commands.jpg`. No outstanding P0/P1/P2 findings for this iteration.
