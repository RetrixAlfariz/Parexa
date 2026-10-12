# Parexa Observatory — working UI refresh

This is an implemented, progressive enhancement of Parexa's existing Flask and vanilla JavaScript frontend, not a screenshot or a new frontend framework.

## Run

With the existing `.env` configured, launch the application from the repository root using `python main.py`. Open the local address printed by Flask (normally `http://127.0.0.1:5000`).

The README's older `python app.py` example is not the actual top-level entry point.

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
