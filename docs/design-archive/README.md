# Archived research-workspace design (October 2026)

The `polish/research-workspace-v1` branch experimented with a terminal-density, square-corner, purple/gray UI.

**Not loaded by Parexa:** `workspace-v1.css` is archived as an intact design reference. Importing it would override the active Parexa Observatory cyan theme and undo its layout. The compatible functionality was forward-ported:

- `website/static/workspace.js`: live mode/web/embedding/request status and keyboard shortcuts;
- `website/static/css/workspace-status.css`: matching status ribbon for the modern Observatory palette;
- safer chat input handling, readable error messages, escaping and bounded conversation lists.

The source branch tip at the time of consolidation was `4107b476e9e4f0ccde600a22a82656e6dac7c842`; its original Git history is also preserved by the integration merge. Do not enable the archived stylesheet in `website/static/styles.css`.
