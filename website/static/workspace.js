/* Parexa workspace live telemetry and keyboard shortcuts, reintroduced on Observatory.
   No duplicated conversation or inference state; only reflect existing controls. */
(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const mode = byId("workspace-mode");
  const browsing = byId("workspace-browsing");
  const embedding = byId("workspace-embedding");
  const runStatus = byId("workspace-run-status");
  const genesisButton = byId("agent-genesis");
  const browseButton = byId("browse-toggle");
  const activityStatus = byId("activity-status");
  const composer = byId("user-input");

  const syncMode = () => {
    if (!mode) return;
    const active = genesisButton?.getAttribute("aria-pressed") === "true";
    mode.textContent = active ? "GENESIS" : "STANDARD";
    mode.dataset.state = active ? "active" : "default";
  };

  const syncBrowsing = () => {
    if (!browsing) return;
    const active = browseButton?.getAttribute("aria-pressed") === "true";
    browsing.textContent = active ? "ON" : "OFF";
    browsing.dataset.state = active ? "active" : "default";
  };

  const syncRunStatus = () => {
    if (!runStatus || !activityStatus) return;
    runStatus.textContent = (activityStatus.textContent || "Ready").toUpperCase();
    runStatus.dataset.state = activityStatus.classList.contains("error")
      ? "error"
      : "default";
  };

  const observe = (element, callback, options) => {
    if (!element) return;
    const observer = new MutationObserver(callback);
    observer.observe(element, options);
  };

  observe(genesisButton, syncMode, {
    attributes: true,
    attributeFilter: ["aria-pressed"],
  });
  observe(browseButton, syncBrowsing, {
    attributes: true,
    attributeFilter: ["aria-pressed"],
  });
  observe(activityStatus, syncRunStatus, {
    attributes: true,
    attributeFilter: ["class"],
    childList: true,
    characterData: true,
    subtree: true,
  });

  let checkingEmbedding = false;
  const checkEmbedding = async () => {
    if (!embedding || checkingEmbedding) return;
    checkingEmbedding = true;
    try {
      const response = await fetch("/api/health/embedding", { cache: "no-store" });
      if (!response.ok) throw new Error("Health endpoint unavailable");
      const result = await response.json();
      const provider = String(result.provider || "unknown")
        .replace(/[^a-z0-9_-]/gi, "")
        .toUpperCase();
      const status = String(result.status || "unknown").toLowerCase();
      if (result.enabled) {
        embedding.textContent = `${provider} / ${status.toUpperCase()}`;
        embedding.dataset.state = status === "ok"
          ? "ok"
          : status === "down" ? "error" : "default";
      } else {
        embedding.textContent = `${provider} / UNCHECKED`;
        embedding.dataset.state = "default";
      }
      embedding.title = result.enabled
        ? "Embedding health is monitored by the backend."
        : "The backend does not monitor health for this embedding provider.";
    } catch {
      embedding.textContent = "UNAVAILABLE";
      embedding.dataset.state = "error";
      embedding.title = "Unable to reach the embedding status endpoint.";
    } finally {
      checkingEmbedding = false;
    }
  };

  const isEditing = (target) =>
    Boolean(
      target?.isContentEditable ||
      target?.closest?.("input, textarea, select, [contenteditable='true']")
    );
  const hasOpenDialog = () =>
    ["modal-overlay", "activity-drawer", "settings-drawer"].some((id) => {
      const element = byId(id);
      return element && !element.hidden;
    });

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented) return;
    const key = event.key.toLowerCase();

    if (
      key === "/" &&
      !event.altKey && !event.shiftKey && !event.ctrlKey && !event.metaKey &&
      !isEditing(event.target) && !hasOpenDialog()
    ) {
      event.preventDefault();
      composer?.focus();
      return;
    }

    if (!event.altKey || event.ctrlKey || event.metaKey || hasOpenDialog()) return;

    if (key === "n" && !event.shiftKey) {
      event.preventDefault();
      document.querySelector(".new-chat-btn")?.click();
    } else if (key === "b" && event.shiftKey) {
      event.preventDefault();
      byId("sidebar-toggle-btn")?.click();
    } else if (key === "p" && event.shiftKey) {
      event.preventDefault();
      byId("panel-toggle-btn")?.click();
    }
  });

  syncMode();
  syncBrowsing();
  syncRunStatus();
  void checkEmbedding();
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void checkEmbedding();
  });
})();
