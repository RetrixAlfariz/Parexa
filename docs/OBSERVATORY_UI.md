# Parexa Observatory — working UI refresh

This is an implemented, progressive enhancement of Parexa's existing Flask and vanilla JavaScript frontend, not a screenshot or a new frontend framework.

## Run

With the existing `.env` configured, launch the application from the repository root using `python main.py`. Open the local address printed by Flask (normally `http://127.0.0.1:5000`).

The README's older `python app.py` example is not the actual top-level entry point.

## Chat folders and branding

The visible product name is **Parexa**. Chat folders can be created, renamed, collapsed, and removed from the sidebar. Each chat has a folder control for moving it between folders and Unfiled. Removing a folder keeps its conversations. Each folder also has a New subfolder control. Subfolders can contain further folders; move menus show full paths. Removing a parent moves its children up one level and preserves their chat assignments. Existing flat folders migrate automatically; invalid or cyclic parent links recover to a visible root. Folder names, parent links, collapsed state, and conversation-ID assignments persist in browser localStorage (`parexa.chat-folders.v1`); server conversation storage is unchanged. This organization is browser-specific and does not synchronize across devices.

## Chat-first studio redesign

The selected conversation-focused design keeps the Parexa logo, uses neutral surfaces and cyan accents, and replaces the illustrated home banner with a compact greeting and four starters. The sidebar holds history and workspace navigation; Standard/Genesis controls sit beside the composer. Sources, Context, model selection, and browser-local Notes open in an optional research desk, closed initially on every viewport. Runtime details appear in Context.

`website/static/css/studio.css` supplies the final visual layer over existing styles. Feather icon files and their MIT license are vendored in `website/static/images/icons/`. No frontend framework or package dependencies were added. Mobile navigation uses a drawer without overwriting the desktop sidebar preference. Settings and activity drawers contain keyboard focus; Escape dismisses overlays.

The fixture browser smoke now covers selected-history reload, model selection, dark mode, citation navigation, notes persistence, and mobile controls. The implementation was also exercised in the Codex browser against this fixture API. These checks do not validate real model inference or document ingestion.

## Implemented

- A new light-first cyan/graphite Observatory theme, with dark mode controlled through the existing Settings drawer.
- The actual Parexa SVG mark is stored at `website/static/images/parexa-mark.svg` and used for the sidebar, header, and assistant avatar.
- An exploration home canvas with four working entry points: upload/analyze, Genesis synthesis, explanation, and research planning.
- Dynamic 'continue research' links sourced from the existing conversation history listing.
- A research inspector with **Sources**, **Context**, and **Notes** tabs. Sources reflect uploaded file attachments and cited locations in the latest successful response.
- Browser-local scratchpad notes, stored in `localStorage` under `parexa.observatory.notes.v1`. Notes are **not** sent as AI context.
- Responsive layout: the research inspector is docked on wide screens and a slide-over on smaller screens; sidebar controls collapse for mobile.
- Ctrl/Cmd+K focuses the chat input. Existing new-chat, chat streaming indicator, uploads and progress, Genesis presets, activity, conversations, and settings handlers are reused.
- Citation chips remain visible after a successful response rather than being immediately replaced by a second history fetch.

## Deliberate constraints

- 'Local' describes where the Parexa web application runs. Chat and embedding providers still follow existing `.env` configuration and may make cloud API calls.
- The inspector displays real source file/page labels returned by the backend, **not** reconstructed PDF pages. A full PDF viewer and global document library need backend source-retention APIs.
- The Sources tab lists attachments **only for the next question**. Previous request files are identified as references, not automatically reattached.
- The Context tab reports the most recent model/provider used and retrieval mode. Full semantic memory, direct per-request model switching and named persistent research workspaces are future architecture work.
- No subscription, paid-upgrade screen, fictional GPU figures, or mock 'offline ready' provider status is included.

## Files

- `website/templates/index.html`: updated markup; existing DOM IDs retained for backward compatibility.
- `website/static/css/observatory.css`: new theme, content hierarchy, home canvas, inspector, mobile styles.
- `website/static/observatory.js`: interaction layer and read-only response inspector.
- `website/static/images/parexa-mark.svg`: user-provided mark with the original path shapes preserved.
- `website/static/script.js`: small compatibility changes to emit source metadata and preserve in-session citations.
- `tests/test_observatory_ui.py`: dependency-free structural checks.
- `tests/observatory_browser_smoke.py`: real Chromium smoke through Playwright, with a deliberately fake backend to test interface behavior.

## Validation

```bash
node --check website/static/script.js
node --check website/static/observatory.js
python -m unittest discover -s tests -p 'test_observatory_ui.py' -v
```

The GitHub Actions `Observatory UI checks` workflow also launches Chromium and tests the upload, reply, source inspector, notes, and responsive navigation flows against a minimal stub API. It uploads desktop, chat, and mobile screenshots as workflow artifacts.

**Not covered by this browser smoke:** real Cerebras/Google responses, LM Studio model inference, OCR, Qdrant, or full RAG correctness. Those require a separate provider-backed integration environment.

The conversation panel now uses the requested expressive cyan treatment: a branded header band, tinted canvas, solid cyan user messages, a distinct Parexa answer surface, and an accented composer. Light/dark tokens and mobile layouts share the same hierarchy. Run `node tests/chat_folders_test.cjs` for nesting and migration regressions.

Scroll areas use native cyan scrollbar styling with light/dark tracks. Fine-pointer devices use local Feather-derived cyan cursor assets, with a filled action variant; editable text keeps the normal text cursor. Touch input is unchanged, and forced-colors mode falls back to system rendering. Scrolling is not intercepted and no cursor animation loop is used.

## Iris-inspired terminal interactions

`website/static/css/terminal.css` is the final interaction layer, grounded in the supplied Iris BTC header and the local Iris terminal tokens. It uses monospaced chrome, compact borders, amber active/focus states, and coordinated light/dark surfaces while retaining Parexa's logo and cyan identity. Text, action, disabled, busy, and range/move cursor assets are served locally; cursor licenses are included beside the assets. Touch and forced-colors fallbacks remain native.

The Commands control opens a searchable native modal with Ctrl/Cmd+K. Arrow keys navigate, Enter runs, and Escape closes only the command dialog and restores focus. Actions delegate to existing chat, model, research, folder, and settings controls. `/` still focuses the composer when no modal is open. No backend APIs or inference routes were added.
