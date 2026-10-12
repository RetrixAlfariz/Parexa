/* Parexa Observatory progressive enhancement.
 * Reuses existing chat, upload, conversation, Genesis, settings and activity handlers.
 * Does not pretend to provide backend workspaces, a PDF viewer, or model switching.
 */
(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const shell = $(".app-shell");
  const panel = $(".chat-panel");
  const chatLog = $("#chat-log");
  const input = $("#user-input");
  const fileInput = $("#file-upload");
  const fileDisplay = $("#file-display-area");
  const newChat = $(".new-chat-btn");
  const conversations = $(".conversation-items");
  const recentList = $("#ob-recent-list");
  const inspector = $("#ob-inspector");
  const inspectorToggle = $("#ob-inspector-toggle");
  const inspectorClose = $("#ob-inspector-close");
  const sourceList = $("#ob-source-list");
  const evidenceList = $("#ob-evidence-list");
  const sourcesCount = $("#ob-source-count");
  const sourcesTotal = $("#ob-inspector-source-count");
  const evidenceCount = $("#ob-evidence-count");
  const providerOutput = $("#ob-provider");
  const modeOutput = $("#ob-execution-mode");
  const embeddingOutput = $("#ob-embedding-status");
  const genesisLabel = $("#ob-genesis-label");
  const notesInput = $("#ob-scratchpad");
  const notesStatus = $("#ob-notes-status");
  const mobileInspector = window.matchMedia("(max-width: 1280px)");

  if (!shell || !panel || !chatLog || !inspector || !input) return;

  let citedSources = [];
  let lastUsedFiles = [];
  const noteKey = "parexa.observatory.notes.v1";

  function createElement(tag, className, textContent) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (textContent !== undefined) element.textContent = textContent;
    return element;
  }

  function emptyMessage(label) {
    return createElement("p", "ob-empty", label);
  }

  function updateHomeVisibility() {
    const hasChat = Boolean(chatLog.querySelector(".message:not(.typing)"));
    panel.classList.toggle("ob-is-home", !hasChat);
    const overview = $('[data-ob-action="home"].ob-nav-link');
    if (overview) overview.classList.toggle("is-selected", !hasChat);
    if (inspectorToggle) {
      inspectorToggle.setAttribute("aria-expanded", String(!mobileInspector.matches || shell.classList.contains("ob-inspector-open")));
    }
  }

  function openInspector(tab = "sources") {
    selectInspectorTab(tab);
    if (mobileInspector.matches) shell.classList.add("ob-inspector-open");
    if (inspectorToggle) inspectorToggle.setAttribute("aria-expanded", "true");
    if (mobileInspector.matches) inspectorClose?.focus();
  }

  function closeInspector() {
    shell.classList.remove("ob-inspector-open");
    if (inspectorToggle) inspectorToggle.setAttribute("aria-expanded", String(!mobileInspector.matches));
    inspectorToggle?.focus();
  }

  function selectInspectorTab(tab) {
    const name = ["sources", "context", "notes"].includes(tab) ? tab : "sources";
    $$("[data-ob-tab]", inspector).forEach((button) => {
      button.setAttribute("aria-selected", String(button.dataset.obTab === name));
      button.tabIndex = button.dataset.obTab === name ? 0 : -1;
    });
    $$("[data-ob-panel]", inspector).forEach((section) => {
      section.hidden = section.dataset.obPanel !== name;
    });
  }

  function showPrompt(text) {
    input.value = text;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  }

  function updateReasoningLabel() {
    const on = $("#agent-genesis")?.getAttribute("aria-pressed") === "true";
    if (genesisLabel) genesisLabel.textContent = on ? "Genesis (multi-agent)" : "Standard";
  }

  function renderRecent() {
    if (!recentList || !conversations) return;
    const buttons = $$(".conversation-item", conversations).slice(0, 4);
    recentList.replaceChildren();
    if (!buttons.length) {
      recentList.appendChild(emptyMessage("Nothing here yet. A new question is a good place to start."));
      return;
    }
    buttons.forEach((original) => {
      const title = $(".conversation-item-title", original)?.textContent?.trim() || "Conversation";
      const button = createElement("button", "ob-recent-item");
      button.type = "button";
      button.appendChild(createElement("span", "", title));
      button.appendChild(createElement("small", "", "Open ↗"));
      button.addEventListener("click", () => original.click());
      recentList.appendChild(button);
    });
  }

  function getPendingFiles() {
    if (!fileDisplay) return [];
    return $$(".file-chip[data-file-id]", fileDisplay)
      .filter((chip) => Boolean(chip.dataset.fileId))
      .map((chip) => ({
        id: chip.dataset.fileId,
        name: chip.dataset.fileName || "Document",
        type: chip.dataset.fileType || "Document",
        status: "Selected for next question"
      }));
  }

  function sourceItem(file) {
    const row = createElement("div", "ob-source-item");
    row.appendChild(createElement("span", "ob-source-icon", "▤"));
    const copy = createElement("div", "ob-source-copy");
    copy.appendChild(createElement("span", "ob-source-name", String(file.name || "Document")));
    copy.appendChild(createElement("span", "ob-source-status", String(file.status || "Used in last answer")));
    row.appendChild(copy);
    return row;
  }

  function renderSources() {
    if (!sourceList || !evidenceList) return;
    const pending = getPendingFiles();
    // Sources from the most recent request remain visible as references only.
    // They are not silently reattached to the next prompt.
    const latest = pending.length
      ? pending
      : lastUsedFiles.map((file) => ({
          name: file.name || "Document",
          type: file.type || "Document",
          status: "Used in last request; not attached to the next one"
        }));
    sourceList.replaceChildren();
    if (!latest.length) {
      sourceList.appendChild(emptyMessage("No document selected. Use Attach a document to begin."));
    } else {
      latest.forEach((file) => sourceList.appendChild(sourceItem(file)));
    }
    const displayCount = pending.length || lastUsedFiles.length;
    if (sourcesTotal) sourcesTotal.textContent = String(displayCount);
    if (sourcesCount) sourcesCount.textContent = String(displayCount);

    evidenceList.replaceChildren();
    if (!citedSources.length) {
      evidenceList.appendChild(emptyMessage("References appear here when the current answer includes sources."));
    } else {
      citedSources.forEach((source) => {
        const row = createElement("div", "ob-evidence-item");
        row.appendChild(createElement("strong", "", String(source.file || "Unknown source")));
        const page = source.page ? "Page " + source.page : "Page not provided";
        const type = source.type ? " · " + source.type : "";
        row.appendChild(createElement("span", "", page + type));
        evidenceList.appendChild(row);
      });
    }
    if (evidenceCount) evidenceCount.textContent = String(citedSources.length);
  }

  function syncEvidenceLinks() {
    $$(".source-chip", chatLog).forEach((chip) => {
      if (chip.dataset.obAccessible === "true") return;
      chip.dataset.obAccessible = "true";
      chip.tabIndex = 0;
      chip.setAttribute("role", "button");
      chip.title = (chip.title || "Source") + " · Show in Sources panel";
      const activate = () => openInspector("sources");
      chip.addEventListener("click", activate);
      chip.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
    });
  }

  async function updateEmbeddingHealth() {
    if (!embeddingOutput) return;
    try {
      const response = await fetch("/api/health/embedding", { cache: "no-store" });
      if (!response.ok) throw new Error("unavailable");
      const payload = await response.json();
      const provider = String(payload.provider || "configured").toLowerCase();
      if (provider === "lmstudio") {
        embeddingOutput.textContent = payload.healthy
          ? "LM Studio · available"
          : "LM Studio · check connection";
      } else {
        embeddingOutput.textContent = provider + " · health not monitored";
      }
    } catch {
      embeddingOutput.textContent = "Not available";
    }
  }

  function handleAction(action) {
    switch (action) {
      case "home":
        newChat?.click();
        closeInspector();
        break;
      case "conversations":
        $(".conversation-list")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        break;
      case "sources":
        openInspector("sources");
        break;
      case "notes":
        openInspector("notes");
        notesInput?.focus();
        break;
      case "activity":
        $("#panel-toggle-btn")?.click();
        break;
      case "analyze":
        showPrompt("Please analyze the attached document and cite the relevant pages.");
        fileInput?.click();
        break;
      case "synthesize":
        if ($("#agent-genesis")?.getAttribute("aria-pressed") !== "true") {
          $("#agent-genesis")?.click();
        }
        updateReasoningLabel();
        showPrompt("Compare these approaches, examine their assumptions, and synthesize the evidence.");
        break;
      case "explain":
        showPrompt("Explain this concept step by step, including assumptions and a worked example: ");
        break;
      case "plan":
        showPrompt("Create a practical, structured research plan for: ");
        break;
      default:
        break;
    }
  }

  $$("[data-ob-action]").forEach((button) => {
    button.addEventListener("click", () => handleAction(button.dataset.obAction));
  });
  $$("[data-ob-tab]", inspector).forEach((button) => {
    button.addEventListener("click", () => selectInspectorTab(button.dataset.obTab));
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const tabs = $$("[data-ob-tab]", inspector);
      const index = tabs.indexOf(button);
      const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      selectInspectorTab(next.dataset.obTab);
      next.focus();
    });
  });
  inspectorToggle?.addEventListener("click", () => {
    if (mobileInspector.matches && shell.classList.contains("ob-inspector-open")) {
      closeInspector();
    } else {
      openInspector("sources");
    }
  });
  inspectorClose?.addEventListener("click", closeInspector);
  $("#ob-add-source")?.addEventListener("click", () => fileInput?.click());
  $("#ob-open-activity")?.addEventListener("click", () => {
    if (mobileInspector.matches) closeInspector();
    $("#panel-toggle-btn")?.click();
  });
  $("#ob-toggle-genesis")?.addEventListener("click", () => {
    const on = $("#agent-genesis")?.getAttribute("aria-pressed") === "true";
    (on ? $("#agent-default") : $("#agent-genesis"))?.click();
    updateReasoningLabel();
  });
  [$("#agent-default"), $("#agent-genesis")].filter(Boolean).forEach((button) => {
    button.addEventListener("click", () => queueMicrotask(updateReasoningLabel));
  });
  newChat?.addEventListener("click", () => {
    citedSources = [];
    lastUsedFiles = [];
    if (providerOutput) providerOutput.textContent = "Not run yet";
    if (modeOutput) modeOutput.textContent = "No request yet";
    renderSources();
    updateHomeVisibility();
  });

  const observer = new MutationObserver(() => {
    updateHomeVisibility();
    syncEvidenceLinks();
  });
  observer.observe(chatLog, { childList: true, subtree: true });
  if (fileDisplay) {
    const uploadObserver = new MutationObserver(renderSources);
    uploadObserver.observe(fileDisplay, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-file-id", "data-file-name", "data-file-type"]
    });
  }
  if (conversations) {
    const recentObserver = new MutationObserver(renderRecent);
    recentObserver.observe(conversations, { childList: true });
  }

  window.addEventListener("parexa:response", (event) => {
    const detail = event.detail || {};
    citedSources = Array.isArray(detail.sources) ? detail.sources : [];
    lastUsedFiles = Array.isArray(detail.files) ? detail.files : [];
    const execution = detail.execution || {};
    if (providerOutput) {
      providerOutput.textContent = [execution.provider, execution.model]
        .filter(Boolean).join(" / ") || "Configured model";
    }
    if (modeOutput) modeOutput.textContent = String(execution.mode || "Chat");
    renderSources();
  });

  function applyInspectorBreakpoint() {
    if (!mobileInspector.matches) shell.classList.remove("ob-inspector-open");
    inspectorToggle?.setAttribute("aria-expanded", String(!mobileInspector.matches || shell.classList.contains("ob-inspector-open")));
  }
  mobileInspector.addEventListener?.("change", applyInspectorBreakpoint);

  if (notesInput) {
    try {
      notesInput.value = localStorage.getItem(noteKey) || "";
    } catch {
      if (notesStatus) notesStatus.textContent = "Browser storage is unavailable.";
    }
    notesInput.addEventListener("input", () => {
      try {
        localStorage.setItem(noteKey, notesInput.value);
        if (notesStatus) notesStatus.textContent = "Saved in this browser. Not included in AI context.";
      } catch {
        if (notesStatus) notesStatus.textContent = "Cannot save notes in this browser.";
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      input.focus();
      input.select();
    }
    if (event.key === "Escape" && shell.classList.contains("ob-inspector-open")) {
      closeInspector();
    }
  });

  updateHomeVisibility();
  renderRecent();
  renderSources();
  updateReasoningLabel();
  applyInspectorBreakpoint();
  updateEmbeddingHealth();
})();
