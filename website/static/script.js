const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");
const chatLog = document.getElementById("chat-log");
const conversationContainer = document.querySelector(".conversation-items");
const conversationEmptyState = document.querySelector(".conversation-empty");
const newChatButton = document.querySelector(".new-chat-btn");
const agentDefaultButton = document.getElementById("agent-default");
const agentGenesisButton = document.getElementById("agent-genesis");
const agentIndicator = document.getElementById("agent-indicator");
const activityFeed = document.getElementById("activity-feed");
const activityStatus = document.getElementById("activity-status");
const activityTokenSummary = document.getElementById("activity-token-summary");
const activityTokenNote = document.getElementById("activity-token-note");
const activityLatency = document.getElementById("activity-latency");
const panelToggleButton = document.getElementById("panel-toggle-btn");
const activityOverlay = document.getElementById("activity-overlay");
const activityDrawer = document.getElementById("activity-drawer");
const activityClose = document.getElementById("activity-close");
const activityAgentBadge = document.getElementById("activity-agent-badge");
const sidebarToggleButton = document.getElementById("sidebar-toggle-btn");
const appShell = document.querySelector(".app-shell");
const sidebar = document.querySelector(".sidebar");
const sidebarSettingsButton = document.getElementById("sidebar-settings-btn");
const settingsOverlay = document.getElementById("settings-overlay");
const settingsDrawer = document.getElementById("settings-drawer");
const settingsClose = document.getElementById("settings-close");
const settingsAgentBadge = document.getElementById("settings-agent-badge");
const settingsTabButtons = document.querySelectorAll(".settings-tab");
const settingsSections = document.querySelectorAll(".settings-section");
const settingsSearchInput = document.getElementById("settings-search");
const settingBrowsingDefault = document.getElementById("setting-browsing-default");
const settingAutoScroll = document.getElementById("setting-auto-scroll");
const settingActivityTimestamps = document.getElementById("setting-activity-timestamps");
const settingThinkingTrace = document.getElementById("setting-thinking-trace");
const settingStyleTone = document.getElementById("setting-style-tone");
const settingStyleToneHint = document.getElementById("setting-style-tone-hint");
const settingUserNickname = document.getElementById("setting-user-nickname");
const settingUserAbout = document.getElementById("setting-user-about");
const settingUserEnabled = document.getElementById("setting-user-enabled");
const resetGeneralButton = document.getElementById("reset-general");
const resetAssistantButton = document.getElementById("reset-assistant");
const resetUserButton = document.getElementById("reset-user");
const clearActivityLogButton = document.getElementById("clear-activity-log");
const assistantInstructionsInput = document.getElementById("setting-assistant-instructions");
const clearAssistantInstructionsButton = document.getElementById("clear-assistant-instructions");
const genesisStatusPill = document.getElementById("genesis-status-pill");
const genesisCriticCountInput = document.getElementById("genesis-critic-count");
const genesisCriticMinusButton = document.getElementById("genesis-critic-minus");
const genesisCriticPlusButton = document.getElementById("genesis-critic-plus");
const genesisCriticsContainer = document.getElementById("genesis-critics");
const genesisTotalAgents = document.getElementById("genesis-total-agents");
const genesisTotalCalls = document.getElementById("genesis-total-calls");
const genesisSynthNameInput = document.getElementById("genesis-synth-name");
const genesisSynthInstructionsInput = document.getElementById("genesis-synth-instructions");
const genesisResetButton = document.getElementById("genesis-reset");
const genesisPresetsContainer = document.getElementById("genesis-presets");
const genesisPresetNewButton = document.getElementById("genesis-preset-new");
const genesisPresetImportButton = document.getElementById("genesis-preset-import");
const genesisPresetExportButton = document.getElementById("genesis-preset-export");
const toastStack = document.getElementById("toast-stack");
const modalOverlay = document.getElementById("modal-overlay");
const modalDialog = document.getElementById("modal-dialog");
const modalTitle = document.getElementById("modal-title");
const modalMessage = document.getElementById("modal-message");
const modalForm = document.getElementById("modal-form");
const modalInput = document.getElementById("modal-input");
const modalTextarea = document.getElementById("modal-textarea");
const modalClose = document.getElementById("modal-close");
const modalCancel = document.getElementById("modal-cancel");
const modalConfirm = document.getElementById("modal-confirm");

const history = [];
let conversationId = sessionStorage.getItem("parexaConversationId") || "";
let conversations = [];
let typingIndicator = null;
let activityLog = [];
let lastRequestMeta = null;
let autoScrollEnabled = localStorage.getItem("parexaAutoScroll") !== "false";
let activityTimestampsEnabled =
  localStorage.getItem("parexaActivityTimestamps") !== "false";
let thinkingTraceEnabled =
  localStorage.getItem("parexaThinkingTrace") !== "false";
let themePreference = localStorage.getItem("parexaTheme") || "light";
let assistantStyle = localStorage.getItem("parexaAssistantStyle") || "default";
let userProfile =
  parseStoredJson(localStorage.getItem("parexaUserProfile")) || {
    enabled: false,
    nickname: "",
    about: "",
  };
let assistantInstructions =
  localStorage.getItem("parexaAssistantInstructions") || "";
let assistantInstructionsSaveTimer = null;
let activeAgent = localStorage.getItem("parexaAgent") || "default";
let genesisConfigSaveTimer = null;
let genesisConfig = null;
let genesisPresetsSaveTimer = null;
const timestampFormatter = new Intl.DateTimeFormat("id-ID", {
  dateStyle: "short",
  timeStyle: "short",
});

if (typeof marked !== "undefined") {
  marked.setOptions({
    breaks: true,
    gfm: true,
  });
}

const escapeHtmlText = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);

const renderMarkdown = (text) => {
  if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
    const rawHtml = marked.parse(text);
    return DOMPurify.sanitize(rawHtml);
  }
  // Marked and DOMPurify are optional CDN assets. Escape content when
  // they are unavailable rather than treating untrusted text as HTML.
  return escapeHtmlText(text).replace(/\n/g, "<br>");
};

const setSettingsSection = (section) => {
  if (!settingsSections.length || !settingsTabButtons.length) return;
  const target = section || "general";
  settingsSections.forEach((node) => {
    const isActive = node.dataset.settingsSection === target;
    node.hidden = !isActive;
  });
  settingsTabButtons.forEach((btn) => {
    const isActive = btn.dataset.settingsTab === target;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  sessionStorage.setItem("parexaSettingsSection", target);
  applySettingsFilter();
};

const applySettingsFilter = () => {
  if (!settingsSearchInput) return;
  const query = String(settingsSearchInput.value || "").trim().toLowerCase();
  const activeSection = Array.from(settingsSections).find((node) => !node.hidden);
  if (!activeSection) return;
  const targets = activeSection.querySelectorAll(
    ".settings-item, .genesis-preset-row, .genesis-presets-actions, .genesis-control, .genesis-summary-item, .genesis-roster-header, .genesis-agent"
  );
  targets.forEach((node) => {
    const text = String(node.textContent || "").toLowerCase();
    const match = !query || text.includes(query);
    node.style.display = match ? "" : "none";
  });
};

const applyThemePreference = () => {
  if (!["system", "light", "dark"].includes(themePreference)) {
    themePreference = "system";
  }
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme =
    themePreference === "system"
      ? prefersDark
        ? "dark"
        : "light"
      : themePreference;
  document.documentElement.setAttribute("data-theme", theme);
  themeOptions.forEach((button) => {
    const isActive = button.dataset.theme === themePreference;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
};

const updateStyleToneHint = () => {
  if (!settingStyleToneHint) return;
  const preset = STYLE_TONE_PRESETS[assistantStyle] || STYLE_TONE_PRESETS.default;
  settingStyleToneHint.textContent = preset.hint;
};

const saveUserProfile = () => {
  try {
    localStorage.setItem("parexaUserProfile", JSON.stringify(userProfile));
  } catch (error) {
    console.warn("Failed to save user profile:", error);
  }
};

const buildAssistantInstructions = () => {
  const parts = [];
  const base = String(assistantInstructions || "").trim();
  if (base) parts.push(base);

  const stylePreset = STYLE_TONE_PRESETS[assistantStyle];
  if (stylePreset && stylePreset.instruction) {
    parts.push(`Style & tone:\n${stylePreset.instruction}`);
  }

  if (userProfile?.enabled) {
    const nickname = String(userProfile.nickname || "").trim();
    const about = String(userProfile.about || "").trim();
    if (nickname || about) {
      const lines = [];
      if (nickname) {
        lines.push(`Preferred name: ${nickname}`);
        lines.push(`Address the user as "${nickname}" when appropriate.`);
      }
      if (about) lines.push(`About: ${about}`);
      lines.push(
        "Use this profile to personalize replies. Do not mention it unless the user asks."
      );
      parts.push(`User profile:\n${lines.join("\n")}`);
    }
  }

  return parts.join("\n\n").trim();
};

const STYLE_TONE_PRESETS = {
  default: {
    hint: "Default response style.",
    instruction: "",
  },
  concise: {
    hint: "Short, direct answers with minimal fluff.",
    instruction: "Be concise and direct. Prefer short sentences and bullets.",
  },
  professional: {
    hint: "Formal and polished tone.",
    instruction: "Use a professional, polished tone. Be precise and structured.",
  },
  friendly: {
    hint: "Warm, approachable tone.",
    instruction: "Use a friendly, warm tone while staying clear and helpful.",
  },
  technical: {
    hint: "Precise, technical language.",
    instruction: "Use precise technical language and include necessary details.",
  },
  creative: {
    hint: "Imaginative but relevant.",
    instruction: "Be creative and exploratory while staying relevant and accurate.",
  },
};

const themeOptions = document.querySelectorAll(".theme-option");

const showToast = ({ title, detail = "", status = "info", timeoutMs = 4500 } = {}) => {
  if (!toastStack) return;
  const toast = document.createElement("div");
  toast.className = "toast";
  if (status) toast.classList.add(status);
  toast.setAttribute("role", status === "error" ? "alert" : "status");

  const body = document.createElement("div");
  body.className = "toast-body";

  const h = document.createElement("p");
  h.className = "toast-title";
  h.textContent = title || "Notification";

  const p = document.createElement("p");
  p.className = "toast-detail";
  p.textContent = detail || "";

  body.appendChild(h);
  if (detail) body.appendChild(p);

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "Dismiss notification");
  close.innerHTML = "&times;";
  close.addEventListener("click", () => toast.remove());

  toast.appendChild(body);
  toast.appendChild(close);
  toastStack.appendChild(toast);

  if (timeoutMs && timeoutMs > 0) {
    setTimeout(() => {
      if (toast.isConnected) toast.remove();
    }, timeoutMs);
  }
};

let activeModalResolve = null;
let activeModalReject = null;
let modalPreviouslyFocused = null;

const getFocusableElements = (root) => {
  if (!root) return [];
  return Array.from(
    root.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
  ).filter((el) => !el.disabled && el.offsetParent !== null);
};

const closeModal = (result) => {
  if (!modalOverlay || !modalDialog) return;
  modalOverlay.hidden = true;
  document.body.style.overflow = "";
  const resolve = activeModalResolve;
  activeModalResolve = null;
  activeModalReject = null;

  if (modalPreviouslyFocused && typeof modalPreviouslyFocused.focus === "function") {
    modalPreviouslyFocused.focus();
  }
  modalPreviouslyFocused = null;
  if (typeof resolve === "function") resolve(Boolean(result));
};

const resetModalForm = () => {
  if (modalForm) modalForm.hidden = true;
  if (modalInput) {
    modalInput.value = "";
    modalInput.hidden = false;
  }
  if (modalTextarea) {
    modalTextarea.value = "";
    modalTextarea.hidden = true;
  }
};

const openConfirmModal = ({
  title = "Confirm",
  message = "Are you sure?",
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
} = {}) => {
  if (!modalOverlay || !modalDialog || !modalTitle || !modalMessage || !modalConfirm || !modalCancel) {
    return Promise.resolve(false);
  }

  modalPreviouslyFocused = document.activeElement;
  resetModalForm();
  modalTitle.textContent = title;
  modalMessage.textContent = message;
  modalConfirm.textContent = confirmLabel;
  modalCancel.textContent = cancelLabel;
  modalConfirm.classList.toggle("modal-btn-danger", Boolean(danger));

  modalOverlay.hidden = false;
  document.body.style.overflow = "hidden";

  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeModal(false);
      return;
    }
    if (event.key === "Tab") {
      const focusables = getFocusableElements(modalDialog);
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !modalDialog.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        event.preventDefault();
        first.focus();
      }
    }
  };

  const onOverlayClick = (event) => {
    if (event.target === modalOverlay) {
      closeModal(false);
    }
  };

  const cleanup = () => {
    document.removeEventListener("keydown", onKeyDown, true);
    modalOverlay.removeEventListener("click", onOverlayClick);
    modalClose?.removeEventListener("click", onCloseClick);
    modalCancel.removeEventListener("click", onCancelClick);
    modalConfirm.removeEventListener("click", onConfirmClick);
  };

  const onCloseClick = () => closeModal(false);
  const onCancelClick = () => closeModal(false);
  const onConfirmClick = () => closeModal(true);

  return new Promise((resolve, reject) => {
    activeModalResolve = (value) => {
      cleanup();
      resolve(value);
    };
    activeModalReject = (err) => {
      cleanup();
      reject(err);
    };

    document.addEventListener("keydown", onKeyDown, true);
    modalOverlay.addEventListener("click", onOverlayClick);
    modalClose?.addEventListener("click", onCloseClick);
    modalCancel.addEventListener("click", onCancelClick);
    modalConfirm.addEventListener("click", onConfirmClick);

    const toFocus = danger ? modalCancel : modalConfirm;
    setTimeout(() => toFocus.focus(), 0);
  });
};

const openPromptModal = async ({
  title = "New preset",
  message = "",
  placeholder = "Preset name",
  initialValue = "",
  confirmLabel = "Save",
  cancelLabel = "Cancel",
  danger = false,
} = {}) => {
  if (
    !modalOverlay ||
    !modalDialog ||
    !modalTitle ||
    !modalMessage ||
    !modalConfirm ||
    !modalCancel ||
    !modalForm ||
    !modalInput
  ) {
    return null;
  }

  modalPreviouslyFocused = document.activeElement;
  resetModalForm();
  modalForm.hidden = false;
  modalInput.hidden = false;
  if (modalTextarea) modalTextarea.hidden = true;

  modalTitle.textContent = title;
  modalMessage.textContent = message;
  modalInput.placeholder = placeholder;
  modalInput.value = initialValue || "";
  modalConfirm.textContent = confirmLabel;
  modalCancel.textContent = cancelLabel;
  modalConfirm.classList.toggle("modal-btn-danger", Boolean(danger));

  modalOverlay.hidden = false;
  document.body.style.overflow = "hidden";

  const getValue = () => String(modalInput.value || "").trim();

  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeModal(false);
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const value = getValue();
      if (!value) return;
      closeModal(true);
      return;
    }
    if (event.key === "Tab") {
      const focusables = getFocusableElements(modalDialog);
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !modalDialog.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        event.preventDefault();
        first.focus();
      }
    }
  };

  const onOverlayClick = (event) => {
    if (event.target === modalOverlay) {
      closeModal(false);
    }
  };

  const cleanup = () => {
    document.removeEventListener("keydown", onKeyDown, true);
    modalOverlay.removeEventListener("click", onOverlayClick);
    modalClose?.removeEventListener("click", onCloseClick);
    modalCancel.removeEventListener("click", onCancelClick);
    modalConfirm.removeEventListener("click", onConfirmClick);
  };

  const onCloseClick = () => closeModal(false);
  const onCancelClick = () => closeModal(false);
  const onConfirmClick = () => {
    const value = getValue();
    if (!value) return;
    closeModal(true);
  };

  const confirmed = await new Promise((resolve, reject) => {
    activeModalResolve = (value) => {
      cleanup();
      resolve(Boolean(value));
    };
    activeModalReject = (err) => {
      cleanup();
      reject(err);
    };

    document.addEventListener("keydown", onKeyDown, true);
    modalOverlay.addEventListener("click", onOverlayClick);
    modalClose?.addEventListener("click", onCloseClick);
    modalCancel.addEventListener("click", onCancelClick);
    modalConfirm.addEventListener("click", onConfirmClick);

    setTimeout(() => modalInput.focus(), 0);
  });

  if (!confirmed) return null;
  const value = getValue();
  return value || null;
};

const openTextareaModal = async ({
  title = "Import",
  message = "",
  placeholder = "Paste JSON here",
  initialValue = "",
  confirmLabel = "Import",
  cancelLabel = "Cancel",
} = {}) => {
  if (
    !modalOverlay ||
    !modalDialog ||
    !modalTitle ||
    !modalMessage ||
    !modalConfirm ||
    !modalCancel ||
    !modalForm ||
    !modalTextarea
  ) {
    return null;
  }

  modalPreviouslyFocused = document.activeElement;
  resetModalForm();
  modalForm.hidden = false;
  if (modalInput) modalInput.hidden = true;
  modalTextarea.hidden = false;

  modalTitle.textContent = title;
  modalMessage.textContent = message;
  modalTextarea.placeholder = placeholder;
  modalTextarea.value = initialValue || "";
  modalConfirm.textContent = confirmLabel;
  modalCancel.textContent = cancelLabel;
  modalConfirm.classList.toggle("modal-btn-danger", false);

  modalOverlay.hidden = false;
  document.body.style.overflow = "hidden";

  const getValue = () => String(modalTextarea.value || "").trim();

  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeModal(false);
      return;
    }
    if (event.key === "Tab") {
      const focusables = getFocusableElements(modalDialog);
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !modalDialog.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        event.preventDefault();
        first.focus();
      }
    }
  };

  const onOverlayClick = (event) => {
    if (event.target === modalOverlay) {
      closeModal(false);
    }
  };

  const cleanup = () => {
    document.removeEventListener("keydown", onKeyDown, true);
    modalOverlay.removeEventListener("click", onOverlayClick);
    modalClose?.removeEventListener("click", onCloseClick);
    modalCancel.removeEventListener("click", onCancelClick);
    modalConfirm.removeEventListener("click", onConfirmClick);
  };

  const onCloseClick = () => closeModal(false);
  const onCancelClick = () => closeModal(false);
  const onConfirmClick = () => {
    const value = getValue();
    if (!value) return;
    closeModal(true);
  };

  const confirmed = await new Promise((resolve, reject) => {
    activeModalResolve = (value) => {
      cleanup();
      resolve(Boolean(value));
    };
    activeModalReject = (err) => {
      cleanup();
      reject(err);
    };

    document.addEventListener("keydown", onKeyDown, true);
    modalOverlay.addEventListener("click", onOverlayClick);
    modalClose?.addEventListener("click", onCloseClick);
    modalCancel.addEventListener("click", onCancelClick);
    modalConfirm.addEventListener("click", onConfirmClick);

    setTimeout(() => modalTextarea.focus(), 0);
  });

  if (!confirmed) return null;
  const value = getValue();
  return value || null;
};

const estimateTokens = (text) => {
  if (!text) return 0;
  const trimmed = String(text).trim();
  if (!trimmed) return 0;
  return Math.max(1, Math.ceil(trimmed.length / 4));
};

const formatDuration = (ms) => {
  if (!ms || Number.isNaN(ms)) return "-";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return `${minutes}m ${remainder}s`;
};

const truncateText = (value, limit = 160) => {
  if (!value) return "";
  const text = String(value);
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}…`;
};

function parseStoredJson(raw) {
  if (!raw || typeof raw !== "string") return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

const clampInt = (value, min, max, fallback) => {
  const n = Number.parseInt(String(value), 10);
  if (Number.isNaN(n)) return fallback;
  return Math.max(min, Math.min(max, n));
};

const getDefaultGenesisConfig = () => ({
  critics: [
    {
      name: "Critic",
      instructions:
        "Critique the draft for correctness and completeness. Point out missing assumptions, edge cases, and unclear parts. Keep it concise and actionable.",
    },
  ],
  synthesizer: {
    name: "Synthesizer",
    instructions:
      "Rewrite the draft into a clear final answer. Apply the critique. Keep important details and be concise.",
  },
});

const buildGenesisPresets = () => [
  {
    id: "balanced",
    label: "Balanced",
    description: "Default critique and concise final answer.",
    config: getDefaultGenesisConfig(),
  },
  {
    id: "strict",
    label: "Strict QA",
    description: "Extra correctness + edge-case scrutiny.",
    config: {
      critics: [
        {
          name: "Accuracy Critic",
          instructions:
            "Audit factual correctness, assumptions, and missing constraints. Flag anything uncertain or ambiguous.",
        },
        {
          name: "Edge-Case Critic",
          instructions:
            "Identify edge cases, failure modes, and risky oversights. Suggest concrete fixes or clarifications.",
        },
      ],
      synthesizer: {
        name: "Synthesizer",
        instructions:
          "Produce a precise final answer. Address critiques explicitly and avoid over-claiming.",
      },
    },
  },
  {
    id: "creative",
    label: "Creative",
    description: "Explore options and novel ideas.",
    config: {
      critics: [
        {
          name: "Idea Critic",
          instructions:
            "Suggest alternative approaches, creative angles, and missing ideas. Keep suggestions concise.",
        },
      ],
      synthesizer: {
        name: "Synthesizer",
        instructions:
          "Deliver a helpful, imaginative response while staying relevant and clear.",
      },
    },
  },
  {
    id: "executive",
    label: "Executive",
    description: "Short, high-signal summary.",
    config: {
      critics: [
        {
          name: "Clarity Critic",
          instructions:
            "Trim fluff, highlight key points, and enforce concise structure (bullets if helpful).",
        },
      ],
      synthesizer: {
        name: "Synthesizer",
        instructions:
          "Return a brief, bullet-focused answer with clear action items or takeaways.",
      },
    },
  },
];

const BUILTIN_GENESIS_PRESETS = buildGenesisPresets();

const getCustomGenesisPresets = () => {
  const raw = parseStoredJson(localStorage.getItem("parexaGenesisPresetsCustom"));
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      id: String(item.id || "").slice(0, 80),
      label: String(item.label || "Custom").slice(0, 60),
      description: String(item.description || "").slice(0, 140),
      config: normalizeGenesisConfig(item.config || {}),
      custom: true,
    }))
    .filter((item) => item.id && item.label);
};

const saveCustomGenesisPresets = (items) => {
  try {
    localStorage.setItem("parexaGenesisPresetsCustom", JSON.stringify(items || []));
  } catch (error) {
    console.warn("Failed to save custom presets:", error);
  }
};

const getAllGenesisPresets = () => {
  const custom = getCustomGenesisPresets();
  return [
    ...BUILTIN_GENESIS_PRESETS.map((p) => ({ ...p, custom: false })),
    ...custom,
  ];
};

const applyAgentUi = () => {
  const isGenesis = activeAgent === "genesis";
  if (agentDefaultButton) {
    agentDefaultButton.setAttribute("aria-pressed", isGenesis ? "false" : "true");
  }
  if (agentGenesisButton) {
    agentGenesisButton.setAttribute("aria-pressed", isGenesis ? "true" : "false");
  }
  [activityAgentBadge, settingsAgentBadge].forEach((badge) => {
    if (!badge) return;
    if (isGenesis) {
      badge.hidden = false;
      badge.textContent = "Genesis";
    } else {
      badge.hidden = true;
      badge.textContent = "";
    }
  });
  if (agentIndicator) {
    if (isGenesis) {
      agentIndicator.hidden = false;
      agentIndicator.textContent = "Genesis • Multi-agent";
    } else {
      agentIndicator.hidden = true;
      agentIndicator.textContent = "";
    }
  }
  if (genesisStatusPill) {
    genesisStatusPill.textContent = isGenesis ? "Active" : "Inactive";
    genesisStatusPill.classList.toggle("active", isGenesis);
    genesisStatusPill.classList.toggle("inactive", !isGenesis);
  }
};

const normalizeGenesisConfig = (candidate) => {
  const defaults = getDefaultGenesisConfig();
  const config = candidate && typeof candidate === "object" ? candidate : defaults;

  const criticsRaw = Array.isArray(config.critics) ? config.critics : defaults.critics;
  const critics = criticsRaw
    .filter((item) => item && typeof item === "object")
    .map((item, index) => ({
      name: String(item.name || `Critic ${index + 1}`).slice(0, 60),
      instructions: String(item.instructions || "").slice(0, 2000),
    }));

  const boundedCount = clampInt(critics.length, 1, 5, 1);
  while (critics.length < boundedCount) {
    critics.push({
      name: `Critic ${critics.length + 1}`,
      instructions: "",
    });
  }
  critics.length = boundedCount;

  const synth = config.synthesizer && typeof config.synthesizer === "object"
    ? config.synthesizer
    : defaults.synthesizer;

  return {
    critics,
    synthesizer: {
      name: String(synth.name || defaults.synthesizer.name).slice(0, 60),
      instructions: String(synth.instructions || defaults.synthesizer.instructions).slice(0, 2000),
    },
  };
};

const serializeGenesisConfig = (config) =>
  JSON.stringify(normalizeGenesisConfig(config));

const findMatchingGenesisPreset = (config) => {
  const signature = serializeGenesisConfig(config);
  return (
    getAllGenesisPresets().find(
      (preset) => serializeGenesisConfig(preset.config) === signature
    )?.id || ""
  );
};

genesisConfig = normalizeGenesisConfig(
  parseStoredJson(localStorage.getItem("parexaGenesisConfig"))
);
let activeGenesisPreset = localStorage.getItem("parexaGenesisPreset") || "";

const scheduleGenesisConfigSave = () => {
  if (genesisConfigSaveTimer) {
    clearTimeout(genesisConfigSaveTimer);
  }
  genesisConfigSaveTimer = setTimeout(() => {
    try {
      localStorage.setItem("parexaGenesisConfig", JSON.stringify(genesisConfig));
    } catch (error) {
      console.warn("Failed to save Genesis config:", error);
    }
  }, 250);
};

const scheduleCustomPresetsSave = (items) => {
  if (genesisPresetsSaveTimer) {
    clearTimeout(genesisPresetsSaveTimer);
  }
  genesisPresetsSaveTimer = setTimeout(() => saveCustomGenesisPresets(items), 150);
};

const renderGenesisPresets = () => {
  if (!genesisPresetsContainer) {
    return;
  }
  genesisPresetsContainer.innerHTML = "";

  const presets = getAllGenesisPresets();
  presets.forEach((preset) => {
    const row = document.createElement("div");
    row.className = "genesis-preset-row";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "genesis-preset";
    button.dataset.preset = preset.id;
    button.setAttribute("aria-pressed", "false");

    const title = document.createElement("span");
    title.className = "genesis-preset-title";
    title.textContent = preset.label;

    const desc = document.createElement("span");
    desc.className = "genesis-preset-desc";
    desc.textContent = preset.description;

    button.appendChild(title);
    button.appendChild(desc);
    button.addEventListener("click", () => {
      genesisConfig = normalizeGenesisConfig(preset.config);
      renderGenesisConfigUi();
      scheduleGenesisConfigSave();
      showToast({
        title: "Preset applied",
        detail: preset.label,
        status: "success",
        timeoutMs: 2200,
      });
      pushActivity({
        title: "Genesis preset applied",
        detail: `${preset.label} selected.`,
        status: "success",
      });
    });

    row.appendChild(button);

    if (preset.custom) {
      const tools = document.createElement("div");
      tools.className = "genesis-preset-tools";

      const saveBtn = document.createElement("button");
      saveBtn.type = "button";
      saveBtn.className = "genesis-preset-tool";
      saveBtn.title = "Update preset from current config";
      saveBtn.setAttribute("aria-label", "Update preset");
      saveBtn.textContent = "⟳";
      saveBtn.addEventListener("click", () => {
        const items = getCustomGenesisPresets();
        const idx = items.findIndex((p) => p.id === preset.id);
        if (idx >= 0) {
          items[idx] = {
            ...items[idx],
            label: preset.label,
            description: preset.description,
            config: normalizeGenesisConfig(genesisConfig),
          };
          scheduleCustomPresetsSave(items);
          renderGenesisPresets();
          updateGenesisPresetSelection();
          showToast({ title: "Preset updated", detail: preset.label, status: "success", timeoutMs: 2200 });
        }
      });

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "genesis-preset-tool danger";
      deleteBtn.title = "Delete preset";
      deleteBtn.setAttribute("aria-label", "Delete preset");
      deleteBtn.textContent = "🗑";
      deleteBtn.addEventListener("click", async () => {
        const ok = await openConfirmModal({
          title: `Delete preset "${preset.label}"?`,
          message: "This will remove the preset from your browser storage.",
          confirmLabel: "Delete",
          cancelLabel: "Cancel",
          danger: true,
        });
        if (!ok) return;
        const items = getCustomGenesisPresets().filter((p) => p.id !== preset.id);
        scheduleCustomPresetsSave(items);
        renderGenesisPresets();
        updateGenesisPresetSelection();
        showToast({ title: "Preset deleted", detail: preset.label, status: "warn", timeoutMs: 2200 });
      });

      tools.appendChild(saveBtn);
      tools.appendChild(deleteBtn);
      row.appendChild(tools);
    }

    genesisPresetsContainer.appendChild(row);
  });
};

const updateGenesisPresetSelection = () => {
  if (!genesisPresetsContainer) {
    return;
  }
  const matchedId = findMatchingGenesisPreset(genesisConfig);
  activeGenesisPreset = matchedId || "";
  try {
    localStorage.setItem("parexaGenesisPreset", activeGenesisPreset);
  } catch (error) {
    console.warn("Failed to save Genesis preset:", error);
  }

  genesisPresetsContainer
    .querySelectorAll(".genesis-preset")
    .forEach((button) => {
      const isActive = button.dataset.preset === activeGenesisPreset;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });

  if (genesisPresetExportButton) {
    genesisPresetExportButton.disabled = !activeGenesisPreset;
  }
};

const updateGenesisSummary = () => {
  const criticCount = genesisConfig?.critics?.length || 1;
  if (genesisTotalAgents) {
    genesisTotalAgents.textContent = String(criticCount + 1);
  }
  if (genesisTotalCalls) {
    genesisTotalCalls.textContent = String(criticCount + 2);
  }
  if (genesisCriticMinusButton) {
    genesisCriticMinusButton.disabled = criticCount <= 1;
  }
  if (genesisCriticPlusButton) {
    genesisCriticPlusButton.disabled = criticCount >= 5;
  }
};

const setGenesisCriticCount = (nextCount) => {
  const bounded = clampInt(nextCount, 1, 5, 1);
  genesisConfig.critics = Array.isArray(genesisConfig.critics)
    ? genesisConfig.critics
    : [];
  while (genesisConfig.critics.length < bounded) {
    genesisConfig.critics.push({
      name: `Critic ${genesisConfig.critics.length + 1}`,
      instructions: "",
    });
  }
  genesisConfig.critics.length = bounded;
  renderGenesisConfigUi();
  scheduleGenesisConfigSave();
};

const renderGenesisConfigUi = () => {
  renderGenesisPresets();
  updateGenesisPresetSelection();
  if (!genesisCriticCountInput || !genesisCriticsContainer || !genesisSynthInstructionsInput) {
    return;
  }

  const criticCount = genesisConfig?.critics?.length || 1;
  genesisCriticCountInput.value = String(criticCount);
  if (genesisSynthNameInput) {
    genesisSynthNameInput.value = genesisConfig?.synthesizer?.name || "";
  }
  genesisSynthInstructionsInput.value = genesisConfig?.synthesizer?.instructions || "";
  updateGenesisSummary();

  genesisCriticsContainer.innerHTML = "";

  (genesisConfig?.critics || []).forEach((critic, index) => {
    const card = document.createElement("div");
    card.className = "genesis-agent";

    const header = document.createElement("div");
    header.className = "genesis-agent-header";

    const title = document.createElement("div");
    title.className = "genesis-agent-title";
    title.textContent = `Critic ${index + 1}`;

    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "genesis-agent-name";
    nameInput.placeholder = "Name (optional)";
    nameInput.value = critic.name || "";
    nameInput.setAttribute("aria-label", `Critic ${index + 1} name`);
    nameInput.addEventListener("input", (event) => {
      genesisConfig.critics[index].name = event.target.value || "";
      scheduleGenesisConfigSave();
    });

    header.appendChild(title);
    header.appendChild(nameInput);

    const instructions = document.createElement("textarea");
    instructions.className = "settings-textarea";
    instructions.rows = 3;
    instructions.placeholder = "Instructions (what should this agent focus on?)";
    instructions.value = critic.instructions || "";
    instructions.setAttribute("aria-label", `Critic ${index + 1} instructions`);
    instructions.addEventListener("input", (event) => {
      genesisConfig.critics[index].instructions = event.target.value || "";
      scheduleGenesisConfigSave();
    });

    card.appendChild(header);
    card.appendChild(instructions);

    genesisCriticsContainer.appendChild(card);
  });
  updateGenesisPresetSelection();
};

const setActivityStatus = (label, isError = false) => {
  if (!activityStatus) return;
  activityStatus.textContent = label;
  activityStatus.classList.toggle("error", isError);
};

const updateActivitySummary = (summary) => {
  if (!summary) return;
  if (activityTokenSummary) {
    activityTokenSummary.textContent = `in ${summary.inputTokens}, out ${summary.outputTokens}, total ${summary.totalTokens}`;
  }
  if (activityTokenNote) {
    activityTokenNote.textContent = summary.estimated ? "Estimated" : "Actual";
  }
  if (activityLatency) {
    activityLatency.textContent = summary.latencyMs ? formatDuration(summary.latencyMs) : "-";
  }
};

const renderActivityFeed = () => {
  if (!activityFeed) return;
  activityFeed.innerHTML = "";

  if (!activityLog.length) {
    const empty = document.createElement("div");
    empty.className = "activity-empty";
    empty.textContent = "Belum ada aktivitas. Kirim pesan untuk melihat log.";
    activityFeed.appendChild(empty);
    return;
  }

  activityLog.forEach((entry) => {
    const titleText = entry.title || "Activity";
    const isGenesisStep = titleText.startsWith("Genesis •");
    const isCollapsible = Boolean(entry.detail) && isGenesisStep;

    const card = document.createElement(isCollapsible ? "details" : "div");
    card.className = "activity-card";
    if (isCollapsible) {
      card.classList.add("activity-card-collapsible");
      if (entry.status === "error") {
        card.open = true;
      }
    }
    if (entry.status) {
      card.classList.add(entry.status);
    }

    const header = document.createElement("div");
    header.className = "activity-card-header";

    const title = document.createElement("div");
    title.className = "activity-card-title";
    title.textContent = titleText;

    const time = document.createElement("div");
    time.className = "activity-card-time";
    if (activityTimestampsEnabled) {
      time.textContent = entry.time
        ? timestampFormatter.format(entry.time)
        : "";
    } else {
      time.style.display = "none";
    }

    header.appendChild(title);
    header.appendChild(time);

    if (isCollapsible) {
      const summary = document.createElement("summary");
      summary.className = "activity-card-summary";
      summary.appendChild(header);

      const caret = document.createElement("span");
      caret.className = "activity-card-caret";
      summary.appendChild(caret);

      card.appendChild(summary);
    } else {
      card.appendChild(header);
    }

    if (entry.detail) {
      const detail = document.createElement("div");
      detail.className = "activity-card-detail";
      detail.textContent = entry.detail;
      card.appendChild(detail);
    }

    activityFeed.appendChild(card);
  });
};

const pushActivity = (entry) => {
  const normalized = {
    title: entry.title || "Activity",
    detail: entry.detail || "",
    status: entry.status || "",
    time: entry.time || new Date(),
  };
  activityLog = [normalized, ...activityLog].slice(0, 50);
  renderActivityFeed();
};

const applyActivityPayload = (activity) => {
  if (!activity || typeof activity !== "object") return;
  if (activity.status) {
    const isError = activity.status.toLowerCase() === "error";
    setActivityStatus(activity.status, isError);
  }
  if (activity.usage) {
    const usage = activity.usage;
    updateActivitySummary({
      inputTokens: usage.input_tokens ?? 0,
      outputTokens: usage.output_tokens ?? 0,
      totalTokens: usage.total_tokens ?? 0,
      estimated: usage.estimated ?? true,
      latencyMs: usage.latency_ms ?? 0,
    });
  }
  if (Array.isArray(activity.steps)) {
    activity.steps.forEach((step) => {
      pushActivity({
        title: step.title || "Step",
        detail: step.detail || "",
        status: step.status || "",
        time: step.time ? new Date(step.time) : new Date(),
      });
    });
  }
};

const applyDrawerState = ({ drawer, overlay, toggleButton, isOpen, openTitle, closeTitle }) => {
  if (!drawer || !overlay) return;
  drawer.hidden = !isOpen;
  overlay.hidden = !isOpen;

  if (toggleButton) {
    toggleButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
    if (openTitle && closeTitle) {
      toggleButton.title = isOpen ? closeTitle : openTitle;
    }
  }
};

const setActivityDrawerOpen = (isOpen) => {
  applyDrawerState({
    drawer: activityDrawer,
    overlay: activityOverlay,
    toggleButton: panelToggleButton,
    isOpen,
    openTitle: "Open panel",
    closeTitle: "Close panel",
  });
  if (isOpen) {
    applyDrawerState({
      drawer: settingsDrawer,
      overlay: settingsOverlay,
      toggleButton: sidebarSettingsButton,
      isOpen: false,
      openTitle: "Open settings",
      closeTitle: "Close settings",
    });
  }
};

const setSettingsDrawerOpen = (isOpen) => {
  applyDrawerState({
    drawer: settingsDrawer,
    overlay: settingsOverlay,
    toggleButton: sidebarSettingsButton,
    isOpen,
    openTitle: "Open settings",
    closeTitle: "Close settings",
  });
  if (isOpen) {
    applyDrawerState({
      drawer: activityDrawer,
      overlay: activityOverlay,
      toggleButton: panelToggleButton,
      isOpen: false,
      openTitle: "Open panel",
      closeTitle: "Close panel",
    });
    const stored = sessionStorage.getItem("parexaSettingsSection") || "general";
    setSettingsSection(stored);
  }
};

const createMessageBubble = (role, text) => {
  const message = document.createElement("div");
  message.classList.add("message", role);
  const content = document.createElement("div");
  content.classList.add("message-content");
  if (role === "model") {
    content.innerHTML = renderMarkdown(text);
  } else {
    content.textContent = text;
  }
  message.appendChild(content);
  return message;
};

const getFileTypeLabel = (filename) => {
  const ext = filename.split(".").pop().toLowerCase();
  if (["csv", "xls", "xlsx"].includes(ext)) return "Spreadsheet";
  if (["pdf"].includes(ext)) return "PDF Document";
  if (["png", "jpg", "jpeg", "webp"].includes(ext)) return "Image";
  if (["md", "markdown"].includes(ext)) return "Markdown";
  if (["txt"].includes(ext)) return "Text File";
  return "File";
};

const createFileAttachmentCard = (file) => {
  const pill = document.createElement("div");
  pill.className = "file-attachment-pill";

  // Icon based on type (simplified)
  let iconColor = "#10b981"; // green for csv/sheets
  let iconPath = "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2L14 8 20 8";

  if (file.type === "PDF Document") {
    iconColor = "#ef4444"; // red
  } else if (file.type === "Image") {
    iconColor = "#f59e0b"; // amber
  } else if (file.type === "Markdown" || file.type === "Text File") {
    iconColor = "#3b82f6"; // blue
  }

  // File type icon SVG
  const fileIconSvg = `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="${iconPath}"></path>
    </svg>
  `;

  // Larger icon for popup
  const fileIconSvgLarge = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="${iconPath}"></path>
    </svg>
  `;

  const safeName = escapeHtmlText(file.name);
  const safeType = escapeHtmlText(file.type);
  pill.innerHTML = `
    <div class="file-icon-small" style="color: ${iconColor}">
      ${fileIconSvg}
    </div>
    <div class="file-name-compact" title="${safeName}">${safeName}</div>
    
    <div class="file-card-popup">
        <div class="file-icon" style="background: ${iconColor}20; color: ${iconColor}">
          ${fileIconSvgLarge}
        </div>
        <div class="file-info">
          <div class="file-name">${safeName}</div>
          <div class="file-type">${safeType}</div>
        </div>
    </div>
  `;
  return pill;
};

const createSourceCitation = (sources) => {
  if (!sources || !sources.length) return null;
  
  const citationContainer = document.createElement("div");
  citationContainer.className = "source-citation";
  
  const citationTitle = document.createElement("div");
  citationTitle.className = "citation-title";
  citationTitle.textContent = "Sources:";
  citationContainer.appendChild(citationTitle);
  
  const sourceList = document.createElement("div");
  sourceList.className = "source-list";
  
  sources.forEach((source, index) => {
    const sourceChip = document.createElement("div");
    sourceChip.className = "source-chip";
    
    const sourceType = source.type ? ` | ${source.type}` : "";
    const sourceText = source.page
      ? `${source.file} (p.${source.page}${sourceType})`
      : `${source.file}${sourceType}`;
    
    sourceChip.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
      </svg>
      <span class="source-text"></span>
    `;
    
    sourceChip.querySelector(".source-text").textContent = sourceText;
    sourceChip.title = `Source: ${sourceText}`;
    sourceChip.setAttribute("aria-label", `Source: ${sourceText}`);
    
    sourceList.appendChild(sourceChip);
  });
  
  citationContainer.appendChild(sourceList);
  return citationContainer;
};

const createThinkingTrace = (trace) => {
  if (!thinkingTraceEnabled) return null;
  if (!Array.isArray(trace) || trace.length === 0) return null;

  const wrapper = document.createElement("details");
  wrapper.className = "thinking-trace";

  const summary = document.createElement("summary");
  summary.className = "thinking-trace-summary";
  summary.textContent = "Thinking";
  wrapper.appendChild(summary);

  const steps = document.createElement("div");
  steps.className = "thinking-trace-steps";

  trace.forEach((step, index) => {
    if (!step || typeof step !== "object") return;
    const title = step.title || `Step ${index + 1}`;
    const content = step.content || "";

    const stepDetails = document.createElement("details");
    stepDetails.className = "thinking-step";

    const stepSummary = document.createElement("summary");
    stepSummary.className = "thinking-step-summary";
    stepSummary.textContent = title;

    const body = document.createElement("div");
    body.className = "thinking-step-body";
    body.innerHTML = renderMarkdown(String(content));

    stepDetails.appendChild(stepSummary);
    stepDetails.appendChild(body);
    steps.appendChild(stepDetails);
  });

  wrapper.appendChild(steps);
  return wrapper;
};

const appendMessage = (
  role,
  text,
  { scroll = true, files = [], sources = [], browsing = false, trace = null } = {}
) => {
  const message = document.createElement("div");
  message.classList.add("message", role);
  if (browsing) {
    message.classList.add("browse-enabled");
  }

  const contentWrapper = document.createElement("div");
  contentWrapper.classList.add("message-content-wrapper");

  // Append files if any (only for user typically, but logic is generic)
  if (files && files.length > 0) {
    const filesContainer = document.createElement("div");
    filesContainer.className = "message-attachments";
    files.forEach(file => {
      filesContainer.appendChild(createFileAttachmentCard(file));
    });
    contentWrapper.appendChild(filesContainer);
  }

  const content = document.createElement("div");
  content.classList.add("message-content");
  if (role === "model") {
    content.innerHTML = renderMarkdown(text);
  } else {
    content.textContent = text;
  }

  contentWrapper.appendChild(content);
  
  // Add source citations if available (only for model responses)
  if (role === "model" && sources && sources.length > 0) {
    const citationElement = createSourceCitation(sources);
    if (citationElement) {
      contentWrapper.appendChild(citationElement);
    }
  }

  if (role === "model" && trace) {
    const traceElement = createThinkingTrace(trace);
    if (traceElement) {
      contentWrapper.appendChild(traceElement);
    }
  }
  
  message.appendChild(contentWrapper);

  chatLog.appendChild(message);
  if (scroll && autoScrollEnabled) {
    chatLog.scrollTop = chatLog.scrollHeight;
  }
};

const showTypingIndicator = () => {
  if (typingIndicator) {
    return;
  }

  const message = document.createElement("div");
  message.className = "message model typing";

  const content = document.createElement("div");
  content.className = "message-content typing-indicator";
  content.setAttribute("aria-label", "Parexa sedang mengetik");
  content.innerHTML = `
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
  `;

  message.appendChild(content);
  chatLog.appendChild(message);
  typingIndicator = message;
  chatLog.scrollTop = chatLog.scrollHeight;
};

const hideTypingIndicator = () => {
  if (!typingIndicator) {
    return;
  }
  typingIndicator.remove();
  typingIndicator = null;
};

const setLoadingState = (isLoading) => {
  const button = form.querySelector("button");
  button.disabled = isLoading;
  // button.textContent = isLoading ? "Mengirim..." : "Kirim"; // Using icon instead
  button.style.opacity = isLoading ? "0.7" : "1";
};

const resetConversationView = () => {
  chatLog.innerHTML = "";
  hideTypingIndicator();
  history.length = 0;
};

const loadConversationFromHistory = (entries) => {
  if (!Array.isArray(entries) || !entries.length) {
    return;
  }
  resetConversationView();
  entries.forEach(({ role, text, files }, index) => {
    appendMessage(role, text, { scroll: index === entries.length - 1, files });
    history.push({ role, text, files });
  });
};

const fetchConversation = async (id) => {
  try {
    const response = await fetch(`/api/conversations/${encodeURIComponent(id)}`);
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (payload.history) {
      loadConversationFromHistory(payload.history);
    }
  } catch (error) {
    console.error("Failed to load conversation history:", error);
  }
};

const formatTimestamp = (value) => {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return timestampFormatter.format(date);
};

const deleteConversation = async (id, label = "") => {
  if (!id) {
    return;
  }
  const title = label ? `Delete "${label}"?` : "Delete chat?";
  const confirmMessage =
    "This will delete this conversation and its history. This action cannot be undone.";
  const ok = await openConfirmModal({
    title,
    message: confirmMessage,
    confirmLabel: "Delete",
    cancelLabel: "Cancel",
    danger: true,
  });
  if (!ok) return;

  try {
    const response = await fetch(`/api/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: id }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || "Gagal menghapus percakapan.");
    }

    conversations = conversations.filter(
      (item) => item?.conversation_id && item.conversation_id !== id
    );

    if (id === conversationId) {
      setConversationId("");
      resetConversationView();
    } else {
      renderConversationList(conversations, conversationId);
    }

    await refreshConversationList(conversationId);
  } catch (error) {
    console.error("Failed to delete conversation:", error);
    showToast({
      title: "Delete failed",
      detail: error.message || "Gagal menghapus percakapan.",
      status: "error",
    });
  }
};

const renderConversationList = (items, activeId = conversationId) => {
  if (!conversationContainer) {
    return;
  }
  conversationContainer.innerHTML = "";

  if (!Array.isArray(items) || !items.length) {
    if (conversationEmptyState) {
      conversationEmptyState.hidden = false;
    }
    return;
  }

  if (conversationEmptyState) {
    conversationEmptyState.hidden = true;
  }
  items.forEach((item) => {
    const id = item?.conversation_id;
    if (!id) {
      return;
    }
    const entry = document.createElement("div");
    entry.className = "conversation-entry";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "conversation-item";
    if (id === activeId) {
      button.classList.add("active");
    }
    button.dataset.conversationId = id;

    const title = document.createElement("span");
    title.className = "conversation-item-title";
    title.textContent = item.title || "Percakapan";

    const preview = document.createElement("span");
    preview.className = "conversation-item-preview";
    preview.textContent = item.preview || "Belum ada pesan.";

    button.appendChild(title);
    button.appendChild(preview);

    const metaText = formatTimestamp(item.updated_at || item.created_at);
    if (metaText) {
      const meta = document.createElement("span");
      meta.className = "conversation-item-meta";
      meta.textContent = metaText;
      button.appendChild(meta);
    }

    button.addEventListener("click", () => {
      if (id !== conversationId) {
        handleConversationSelect(id);
      }
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "conversation-item-delete";
    deleteButton.title = "Hapus percakapan";
    deleteButton.setAttribute("aria-label", "Hapus percakapan");
    deleteButton.innerHTML = "&times;";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteConversation(id, item.title || "Percakapan");
    });

    entry.appendChild(button);
    entry.appendChild(deleteButton);
    conversationContainer.appendChild(entry);
  });
};

const setConversationId = (value) => {
  conversationId = value ? String(value) : "";
  if (conversationId) {
    sessionStorage.setItem("parexaConversationId", conversationId);
  } else {
    sessionStorage.removeItem("parexaConversationId");
  }
  renderConversationList(conversations, conversationId);
};

const refreshConversationList = async (activeId = conversationId) => {
  if (!conversationContainer) {
    return;
  }
  try {
    const response = await fetch("/api/conversations?limit=100");
    if (!response.ok) {
      throw new Error(`Gagal memuat percakapan (${response.status}).`);
    }
    const payload = await response.json();
    conversations = Array.isArray(payload.conversations)
      ? payload.conversations
      : [];
    renderConversationList(conversations, activeId);
  } catch (error) {
    console.error("Failed to load conversation list:", error);
  }
};

const handleConversationSelect = async (id) => {
  if (!id) {
    return;
  }
  setConversationId(id);
  await fetchConversation(id);
  await refreshConversationList(id);
};

if (newChatButton) {
  newChatButton.addEventListener("click", () => {
    setConversationId("");
    resetConversationView();
    pushActivity({
      title: "New chat started",
      detail: "Percakapan baru dimulai.",
      status: "success",
    });
    input.focus();
  });
}

applyAgentUi();
renderGenesisConfigUi();
updateGenesisPresetSelection();

if (sidebarSettingsButton) {
  sidebarSettingsButton.addEventListener("click", () => {
    const isOpen = settingsDrawer && !settingsDrawer.hidden;
    setSettingsDrawerOpen(!isOpen);
    if (!isOpen) {
      setSettingsSection("general");
    }
  });
}

const makePresetId = () => `preset_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

const createCustomPresetFromCurrent = async () => {
  const name = await openPromptModal({
    title: "New preset",
    message: "Save the current Genesis configuration as a preset.",
    placeholder: "Preset name",
    confirmLabel: "Save",
    cancelLabel: "Cancel",
  });
  if (!name) return;

  const items = getCustomGenesisPresets();
  const id = makePresetId();
  items.push({
    id,
    label: name,
    description: "Custom preset.",
    config: normalizeGenesisConfig(genesisConfig),
  });
  scheduleCustomPresetsSave(items);
  renderGenesisPresets();
  updateGenesisPresetSelection();
  showToast({ title: "Preset saved", detail: name, status: "success", timeoutMs: 2200 });
};

const importCustomPreset = async () => {
  const raw = await openTextareaModal({
    title: "Import preset",
    message:
      "Paste JSON for a Genesis config (`{ critics, synthesizer }`) or a preset (`{ label, description, config }`) or an array of presets.",
    placeholder: "Paste JSON…",
    confirmLabel: "Import",
    cancelLabel: "Cancel",
  });
  if (!raw) return;

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    showToast({ title: "Invalid JSON", detail: error.message || "Failed to parse JSON.", status: "error" });
    return;
  }

  const toPreset = (value) => {
    if (!value || typeof value !== "object") return null;
    const hasConfig = value.config && typeof value.config === "object";
    const maybeConfig = hasConfig ? value.config : value;
    const normalized = normalizeGenesisConfig(maybeConfig);
    const label = String(value.label || value.name || "Imported preset").slice(0, 60);
    const description = String(value.description || "Imported preset.").slice(0, 140);
    return {
      id: String(value.id || makePresetId()).slice(0, 80),
      label,
      description,
      config: normalized,
    };
  };

  const imported = Array.isArray(parsed)
    ? parsed.map(toPreset).filter(Boolean)
    : [toPreset(parsed)].filter(Boolean);

  if (!imported.length) {
    showToast({ title: "Nothing imported", detail: "JSON format not recognized.", status: "warn" });
    return;
  }

  const existing = getCustomGenesisPresets();
  const existingIds = new Set(existing.map((p) => p.id));
  const merged = [...existing];
  imported.forEach((preset) => {
    let id = preset.id;
    while (existingIds.has(id)) {
      id = makePresetId();
    }
    existingIds.add(id);
    merged.push({ ...preset, id });
  });

  scheduleCustomPresetsSave(merged);
  renderGenesisPresets();
  updateGenesisPresetSelection();
  showToast({ title: "Imported presets", detail: String(imported.length), status: "success", timeoutMs: 2200 });
};

const exportActivePreset = async () => {
  if (!activeGenesisPreset) return;
  const preset = getAllGenesisPresets().find((p) => p.id === activeGenesisPreset);
  if (!preset) return;
  const payload = JSON.stringify(
    { label: preset.label, description: preset.description, config: preset.config },
    null,
    2
  );
  try {
    await navigator.clipboard.writeText(payload);
    showToast({ title: "Preset copied", detail: "Copied JSON to clipboard.", status: "success", timeoutMs: 2200 });
  } catch {
    showToast({ title: "Copy failed", detail: payload, status: "warn", timeoutMs: 8000 });
  }
};

if (genesisPresetNewButton) {
  genesisPresetNewButton.addEventListener("click", () => createCustomPresetFromCurrent());
}
if (genesisPresetImportButton) {
  genesisPresetImportButton.addEventListener("click", () => importCustomPreset());
}
if (genesisPresetExportButton) {
  genesisPresetExportButton.addEventListener("click", () => exportActivePreset());
}

const setActiveAgent = (agent) => {
  const next = agent === "genesis" ? "genesis" : "default";
  if (next === activeAgent) {
    return;
  }
  activeAgent = next;
  localStorage.setItem("parexaAgent", activeAgent);
  applyAgentUi();
  pushActivity({
    title: "Agent switched",
    detail: activeAgent === "genesis" ? "Genesis (Multi-agent)" : "Standard",
    status: "success",
  });
};

if (agentDefaultButton) {
  agentDefaultButton.addEventListener("click", () => setActiveAgent("default"));
}

if (agentGenesisButton) {
  agentGenesisButton.addEventListener("click", () => {
    setActiveAgent(activeAgent === "genesis" ? "default" : "genesis");
  });
}

if (genesisCriticCountInput) {
  genesisCriticCountInput.addEventListener("change", (event) => {
    const nextCount = clampInt(event.target.value, 1, 5, 1);
    event.target.value = String(nextCount);
    setGenesisCriticCount(nextCount);
  });
}

if (genesisCriticMinusButton) {
  genesisCriticMinusButton.addEventListener("click", () => {
    const currentCount = genesisConfig?.critics?.length || 1;
    setGenesisCriticCount(currentCount - 1);
  });
}

if (genesisCriticPlusButton) {
  genesisCriticPlusButton.addEventListener("click", () => {
    const currentCount = genesisConfig?.critics?.length || 1;
    setGenesisCriticCount(currentCount + 1);
  });
}

if (genesisSynthNameInput) {
  genesisSynthNameInput.addEventListener("input", (event) => {
    genesisConfig.synthesizer = genesisConfig.synthesizer || {};
    genesisConfig.synthesizer.name = event.target.value || "";
    scheduleGenesisConfigSave();
  });
}

if (genesisSynthInstructionsInput) {
  genesisSynthInstructionsInput.addEventListener("input", (event) => {
    genesisConfig.synthesizer = genesisConfig.synthesizer || {};
    genesisConfig.synthesizer.instructions = event.target.value || "";
    scheduleGenesisConfigSave();
  });
}

if (genesisResetButton) {
  genesisResetButton.addEventListener("click", () => {
    genesisConfig = normalizeGenesisConfig(getDefaultGenesisConfig());
    renderGenesisConfigUi();
    scheduleGenesisConfigSave();
    pushActivity({
      title: "Genesis config reset",
      detail: "Defaults restored (local only).",
      status: "success",
    });
  });
}

const scheduleConversationRefresh = () => {
  const run = () => refreshConversationList(conversationId);
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(run, { timeout: 1200 });
  } else {
    setTimeout(run, 400);
  }
};

renderActivityFeed();
scheduleConversationRefresh();

if (panelToggleButton) {
  panelToggleButton.addEventListener("click", () => {
    const isOpen = activityDrawer && !activityDrawer.hidden;
    setActivityDrawerOpen(!isOpen);
  });
}

if (activityClose) {
  activityClose.addEventListener("click", () => setActivityDrawerOpen(false));
}

if (activityOverlay) {
  activityOverlay.addEventListener("click", () => setActivityDrawerOpen(false));
}

if (settingsClose) {
  settingsClose.addEventListener("click", () => setSettingsDrawerOpen(false));
}

if (settingsOverlay) {
  settingsOverlay.addEventListener("click", () => setSettingsDrawerOpen(false));
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const activityOpen = activityDrawer && !activityDrawer.hidden;
  const settingsOpen = settingsDrawer && !settingsDrawer.hidden;
  if (activityOpen) setActivityDrawerOpen(false);
  if (settingsOpen) setSettingsDrawerOpen(false);
});

// Default to hidden (user can open via header button).
setActivityDrawerOpen(false);
setSettingsDrawerOpen(false);

const setSidebarHidden = (isHidden) => {
  if (!appShell || !sidebarToggleButton) {
    return;
  }
  appShell.classList.toggle("sidebar-collapsed", isHidden);
  sidebarToggleButton.setAttribute("aria-pressed", isHidden ? "true" : "false");
  sidebarToggleButton.title = isHidden ? "Show sidebar" : "Hide sidebar";
  if (sidebar) {
    sidebar.setAttribute("aria-hidden", isHidden ? "true" : "false");
  }
  localStorage.setItem("parexaSidebarHidden", isHidden ? "true" : "false");
};

const initialSidebarHidden =
  localStorage.getItem("parexaSidebarHidden") === "true";
setSidebarHidden(initialSidebarHidden);

if (sidebarToggleButton) {
  sidebarToggleButton.addEventListener("click", () => {
    const isHidden = appShell?.classList.contains("sidebar-collapsed");
    setSidebarHidden(!isHidden);
  });
}

const fileInput = document.getElementById("file-upload");
const fileDisplayArea = document.getElementById("file-display-area");
const browseToggle = document.getElementById("browse-toggle");
let uploadedFiles = []; // Store objects: { id, name, type }
const BROWSING_PREF_VERSION_KEY = "parexaBrowsingPrefVersion";
const BROWSING_PREF_VERSION = "2";
if (localStorage.getItem(BROWSING_PREF_VERSION_KEY) !== BROWSING_PREF_VERSION) {
  localStorage.setItem("parexaBrowsingEnabled", "false");
  localStorage.setItem(BROWSING_PREF_VERSION_KEY, BROWSING_PREF_VERSION);
}
let browsingEnabled =
  localStorage.getItem("parexaBrowsingEnabled") === "true";
const ALLOWED_UPLOAD_EXTENSIONS = new Set(["txt", "pdf", "md"]);

const isAllowedUploadFile = (filename) => {
  const ext = String(filename || "").split(".").pop().toLowerCase();
  return ALLOWED_UPLOAD_EXTENSIONS.has(ext);
};

const clampUploadPercent = (value) => {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return 1;
  return Math.max(1, Math.min(100, Math.round(numeric)));
};

const buildUploadingFileChip = (filename) => {
  const chip = document.createElement("div");
  chip.className = "file-chip uploading";

  const mainRow = document.createElement("div");
  mainRow.className = "file-chip-main";

  const nameEl = document.createElement("span");
  nameEl.className = "file-name";
  nameEl.textContent = filename;

  const percentEl = document.createElement("span");
  percentEl.className = "file-progress-label";
  percentEl.textContent = "1%";

  mainRow.appendChild(nameEl);
  mainRow.appendChild(percentEl);

  const progressTrack = document.createElement("div");
  progressTrack.className = "file-progress-track";
  const progressFill = document.createElement("div");
  progressFill.className = "file-progress-fill";
  progressFill.style.width = "1%";
  progressTrack.appendChild(progressFill);

  const statusEl = document.createElement("span");
  statusEl.className = "file-status-text";
  statusEl.textContent = "Uploading...";

  chip.appendChild(mainRow);
  chip.appendChild(progressTrack);
  chip.appendChild(statusEl);

  return { chip, percentEl, progressFill, statusEl };
};

const uploadFileWithProgress = (
  file,
  { uploadId, onUploadProgress, onProcessingStart } = {}
) =>
  new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");
    xhr.responseType = "text";
    if (uploadId) {
      xhr.setRequestHeader("X-Upload-ID", uploadId);
    }

    let processingNotified = false;
    const notifyProcessing = () => {
      if (processingNotified) return;
      processingNotified = true;
      if (typeof onProcessingStart === "function") {
        onProcessingStart();
      }
    };

    xhr.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) return;
      if (typeof onUploadProgress === "function") {
        onUploadProgress(event.loaded, event.total);
      }
    });

    xhr.upload.addEventListener("load", notifyProcessing);

    xhr.onreadystatechange = () => {
      if (xhr.readyState >= XMLHttpRequest.HEADERS_RECEIVED) {
        notifyProcessing();
      }
    };

    xhr.onload = () => {
      notifyProcessing();
      let data = {};
      try {
        data = JSON.parse(xhr.responseText || "{}");
      } catch {
        data = {};
      }
      resolve({
        ok: xhr.status >= 200 && xhr.status < 300,
        status: xhr.status,
        data,
      });
    };

    xhr.onerror = () => {
      reject(new Error("Network error during upload"));
    };

    xhr.onabort = () => {
      reject(new Error("Upload cancelled"));
    };

    xhr.send(formData);
  });

const createUploadTrackingId = () => {
  try {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
      return globalThis.crypto.randomUUID();
    }
  } catch {
    // Ignore and fallback.
  }
  return `upload_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
};

const startUploadProgressPolling = (
  uploadId,
  { onProgress, intervalMs = 400 } = {}
) => {
  let cancelled = false;
  let timerId = null;

  const schedule = () => {
    if (cancelled) return;
    timerId = setTimeout(poll, intervalMs);
  };

  const poll = async () => {
    if (cancelled) return;
    try {
      const response = await fetch(
        `/api/upload/progress/${encodeURIComponent(uploadId)}`
      );
      if (cancelled) return;
      if (response.ok) {
        const payload = await response.json();
        if (cancelled) return;
        if (typeof onProgress === "function") {
          onProgress(payload);
        }
        const state = String(payload?.state || "running");
        if (state === "completed" || state === "failed") {
          cancelled = true;
          return;
        }
      }
    } catch {
      // Keep polling until request completes or caller stops it.
    }
    if (cancelled) return;
    schedule();
  };

  poll();
  return () => {
    cancelled = true;
    if (timerId) clearTimeout(timerId);
  };
};

const updateBrowseToggle = () => {
  if (!browseToggle) {
    return;
  }
  browseToggle.setAttribute("aria-pressed", browsingEnabled ? "true" : "false");
  browseToggle.title = browsingEnabled ? "Browsing aktif" : "Aktifkan Browsing";
};

if (browseToggle) {
  updateBrowseToggle();
  browseToggle.addEventListener("click", () => {
    browsingEnabled = !browsingEnabled;
    localStorage.setItem(
      "parexaBrowsingEnabled",
      browsingEnabled ? "true" : "false"
    );
    updateBrowseToggle();
    if (settingBrowsingDefault) {
      settingBrowsingDefault.checked = browsingEnabled;
    }
  });
}

const hydrateSettings = () => {
  if (settingBrowsingDefault) {
    settingBrowsingDefault.checked = browsingEnabled;
  }
  if (settingAutoScroll) {
    settingAutoScroll.checked = autoScrollEnabled;
  }
  if (settingActivityTimestamps) {
    settingActivityTimestamps.checked = activityTimestampsEnabled;
  }
  if (settingThinkingTrace) {
    settingThinkingTrace.checked = thinkingTraceEnabled;
  }
  applyThemePreference();
  if (!STYLE_TONE_PRESETS[assistantStyle]) {
    assistantStyle = "default";
  }
  if (settingStyleTone) {
    settingStyleTone.value = assistantStyle;
    updateStyleToneHint();
  }
  if (settingUserNickname) {
    settingUserNickname.value = userProfile.nickname || "";
  }
  if (settingUserAbout) {
    settingUserAbout.value = userProfile.about || "";
  }
  if (settingUserEnabled) {
    settingUserEnabled.checked = Boolean(userProfile.enabled);
  }
  if (assistantInstructionsInput) {
    assistantInstructionsInput.value = assistantInstructions;
  }
};

if (settingBrowsingDefault) {
  settingBrowsingDefault.addEventListener("change", (event) => {
    browsingEnabled = event.target.checked;
    localStorage.setItem(
      "parexaBrowsingEnabled",
      browsingEnabled ? "true" : "false"
    );
    updateBrowseToggle();
  });
}

settingsTabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setSettingsSection(button.dataset.settingsTab || "general");
  });
});

if (settingsSearchInput) {
  settingsSearchInput.addEventListener("input", () => {
    applySettingsFilter();
  });
}

themeOptions.forEach((button) => {
  button.addEventListener("click", () => {
    themePreference = button.dataset.theme || "system";
    localStorage.setItem("parexaTheme", themePreference);
    applyThemePreference();
  });
});

window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", () => {
    if (themePreference === "system") {
      applyThemePreference();
    }
  });

if (settingStyleTone) {
  settingStyleTone.addEventListener("change", (event) => {
    assistantStyle = event.target.value || "default";
    localStorage.setItem("parexaAssistantStyle", assistantStyle);
    updateStyleToneHint();
  });
}

if (settingUserNickname) {
  settingUserNickname.addEventListener("input", (event) => {
    userProfile.nickname = event.target.value || "";
    saveUserProfile();
  });
}

if (settingUserAbout) {
  settingUserAbout.addEventListener("input", (event) => {
    userProfile.about = event.target.value || "";
    saveUserProfile();
  });
}

if (settingUserEnabled) {
  settingUserEnabled.addEventListener("change", (event) => {
    userProfile.enabled = Boolean(event.target.checked);
    saveUserProfile();
  });
}

if (settingAutoScroll) {
  settingAutoScroll.addEventListener("change", (event) => {
    autoScrollEnabled = event.target.checked;
    localStorage.setItem("parexaAutoScroll", autoScrollEnabled ? "true" : "false");
  });
}

if (settingActivityTimestamps) {
  settingActivityTimestamps.addEventListener("change", (event) => {
    activityTimestampsEnabled = event.target.checked;
    localStorage.setItem(
      "parexaActivityTimestamps",
      activityTimestampsEnabled ? "true" : "false"
    );
    renderActivityFeed();
  });
}

if (settingThinkingTrace) {
  settingThinkingTrace.addEventListener("change", (event) => {
    thinkingTraceEnabled = event.target.checked;
    localStorage.setItem(
      "parexaThinkingTrace",
      thinkingTraceEnabled ? "true" : "false"
    );
  });
}

if (resetGeneralButton) {
  resetGeneralButton.addEventListener("click", () => {
    browsingEnabled = false;
    autoScrollEnabled = true;
    activityTimestampsEnabled = true;
    thinkingTraceEnabled = true;
    themePreference = "system";
    localStorage.setItem("parexaBrowsingEnabled", "false");
    localStorage.setItem("parexaAutoScroll", "true");
    localStorage.setItem("parexaActivityTimestamps", "true");
    localStorage.setItem("parexaThinkingTrace", "true");
    localStorage.setItem("parexaTheme", themePreference);
    updateBrowseToggle();
    hydrateSettings();
    renderActivityFeed();
    showToast({ title: "General settings reset", status: "success", timeoutMs: 2000 });
  });
}

if (resetAssistantButton) {
  resetAssistantButton.addEventListener("click", () => {
    assistantStyle = "default";
    assistantInstructions = "";
    localStorage.setItem("parexaAssistantStyle", assistantStyle);
    localStorage.setItem("parexaAssistantInstructions", "");
    hydrateSettings();
    showToast({ title: "Assistant settings reset", status: "success", timeoutMs: 2000 });
  });
}

if (resetUserButton) {
  resetUserButton.addEventListener("click", () => {
    userProfile = { enabled: false, nickname: "", about: "" };
    saveUserProfile();
    hydrateSettings();
    showToast({ title: "User profile reset", status: "success", timeoutMs: 2000 });
  });
}

if (clearActivityLogButton) {
  clearActivityLogButton.addEventListener("click", () => {
    activityLog = [];
    renderActivityFeed();
    setActivityStatus("Ready");
    updateActivitySummary({
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
      estimated: true,
      latencyMs: 0,
    });
  });
}

if (assistantInstructionsInput) {
  assistantInstructionsInput.addEventListener("input", (event) => {
    const value = event.target.value || "";
    assistantInstructions = value;
    if (assistantInstructionsSaveTimer) {
      clearTimeout(assistantInstructionsSaveTimer);
    }
    assistantInstructionsSaveTimer = setTimeout(() => {
      localStorage.setItem("parexaAssistantInstructions", assistantInstructions);
    }, 250);
  });
}

if (clearAssistantInstructionsButton) {
  clearAssistantInstructionsButton.addEventListener("click", () => {
    assistantInstructions = "";
    localStorage.setItem("parexaAssistantInstructions", "");
    if (assistantInstructionsInput) {
      assistantInstructionsInput.value = "";
    }
    showToast({ title: "Instructions cleared", status: "success", timeoutMs: 2000 });
    pushActivity({
      title: "Assistant instructions cleared",
      detail: "Custom instructions removed (local only).",
      status: "success",
    });
  });
}

hydrateSettings();
setSettingsSection(sessionStorage.getItem("parexaSettingsSection") || "general");

fileInput.addEventListener("change", async (event) => {
  const files = event.target.files;
  if (!files.length) return;

  fileDisplayArea.hidden = false;

  for (const file of files) {
    if (!isAllowedUploadFile(file.name)) {
      const detail = `Unsupported file type for ${file.name}. Allowed: .txt, .pdf, .md`;
      showToast({
        title: "Upload blocked",
        detail,
        status: "warn",
        timeoutMs: 4500,
      });
      pushActivity({
        title: "File upload blocked",
        detail,
        status: "warn",
      });
      continue;
    }

    const { chip: fileChip, percentEl, progressFill, statusEl } =
      buildUploadingFileChip(file.name);
    fileDisplayArea.appendChild(fileChip);
    const uploadTrackingId = createUploadTrackingId();

    let visualProgress = 1;
    let stopProgressPolling = null;
    const setProgress = (value, { statusText, processing } = {}) => {
      visualProgress = Math.max(1, Math.min(100, Number(value) || 1));
      const rounded = clampUploadPercent(visualProgress);
      percentEl.textContent = `${rounded}%`;
      progressFill.style.width = `${rounded}%`;
      if (typeof statusText === "string") {
        statusEl.textContent = statusText;
      }
      fileChip.classList.toggle("processing", Boolean(processing));
    };

    const stopProgressTracking = () => {
      if (typeof stopProgressPolling === "function") {
        stopProgressPolling();
      }
      stopProgressPolling = null;
      fileChip.classList.remove("processing");
    };

    try {
      const response = await uploadFileWithProgress(file, {
        uploadId: uploadTrackingId,
        onUploadProgress: (loaded, total) => {
          const ratio = total > 0 ? loaded / total : 0;
          const uploadProgress = Math.max(1, Math.min(9, 1 + ratio * 8));
          setProgress(uploadProgress, { statusText: "Uploading..." });
        },
        onProcessingStart: () => {
          setProgress(Math.max(visualProgress, 10), {
            statusText: "Server processing...",
            processing: true,
          });
          if (stopProgressPolling) return;
          stopProgressPolling = startUploadProgressPolling(uploadTrackingId, {
            onProgress: (payload) => {
              const backendPercent = Number(payload?.percent);
              const backendMessage = String(payload?.message || "Processing...");
              const state = String(payload?.state || "running");
              const effectivePercent = Number.isFinite(backendPercent)
                ? Math.max(10, backendPercent)
                : Math.max(visualProgress, 10);
              setProgress(effectivePercent, {
                statusText: backendMessage,
                processing: state === "running",
              });
            },
          });
        },
      });

      const data = response.data || {};
      stopProgressTracking();
      if (response.ok) {
        setProgress(100, { statusText: "Done", processing: false });
        fileChip.classList.remove("uploading");
        const filename = data.filename || file.name;
        fileChip.innerHTML = `
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span class="file-name">${filename}</span>
          <button type="button" class="remove-file" aria-label="Remove file">×</button>
        `;

        const fileObj = {
          id: data.file_id,
          name: filename,
          type: getFileTypeLabel(filename)
        };
        fileChip.dataset.fileId = data.file_id;
        fileChip.dataset.fileName = filename;
        fileChip.dataset.fileType = getFileTypeLabel(filename);

        // Add remove listener
        fileChip.querySelector(".remove-file").addEventListener("click", () => {
          uploadedFiles = uploadedFiles.filter(f => f.id !== data.file_id);
          fileChip.remove();
          if (uploadedFiles.length === 0) {
            fileDisplayArea.hidden = true;
          }
        });

        uploadedFiles.push(fileObj);
        pushActivity({
          title: "File uploaded",
          detail: `${filename} (${fileObj.type})`,
          status: "success",
        });

        const uploadWarnings = Array.isArray(data.warnings) ? data.warnings : [];
        uploadWarnings.forEach((warningText) => {
          const detail = String(warningText || "").trim();
          if (!detail) return;
          showToast({
            title: "Upload warning",
            detail,
            status: "warn",
            timeoutMs: 6000,
          });
          pushActivity({
            title: "Upload warning",
            detail,
            status: "warn",
          });
        });

        const ingestion = data.ingestion && typeof data.ingestion === "object" ? data.ingestion : null;
        if (ingestion) {
          const pagesTotal = Number(ingestion.pages_total || 0);
          const pagesProcessed = Number(ingestion.pages_processed || 0);
          const ocrPages = Number(ingestion.ocr_pages || 0);
          const nodesCreated = Number(ingestion.nodes_created || 0);
          const economyMode = Boolean(ingestion.economy_mode);
          const statsLine =
            `pages ${pagesProcessed}/${pagesTotal} · OCR ${ocrPages} · nodes ${nodesCreated}` +
            (economyMode ? " · economy mode" : "");
          pushActivity({
            title: "Ingestion stats",
            detail: `${filename}\n${statsLine}`,
            status: economyMode ? "warn" : "info",
          });
        }
      } else {
        stopProgressTracking();
        fileChip.classList.remove("uploading");
        fileChip.textContent = `Error: ${data.error || "Upload failed"}`;
        fileChip.classList.add("error");
        setTimeout(() => fileChip.remove(), 3000);
        pushActivity({
          title: "File upload failed",
          detail: data.error || "Upload failed",
          status: "error",
        });
      }
    } catch (error) {
      stopProgressTracking();
      console.error("Upload error:", error);
      fileChip.classList.remove("uploading");
      fileChip.textContent = "Upload failed";
      fileChip.classList.add("error");
      setTimeout(() => fileChip.remove(), 3000);
      pushActivity({
        title: "File upload failed",
        detail: error.message || "Upload failed",
        status: "error",
      });
    }
  }

  fileInput.value = "";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message && uploadedFiles.length === 0) {
    return;
  }

  const currentFiles = [...uploadedFiles];
  if (!message && currentFiles.length > 0) {
    showToast({
      title: "Tambahkan pertanyaan",
      detail: "File sudah terlampir. Tulis pertanyaan agar dokumen dipakai untuk RAG.",
      status: "warn",
      timeoutMs: 4500,
    });
    pushActivity({
      title: "Request blocked",
      detail: "File terlampir tanpa pertanyaan tidak dikirim.",
      status: "warn",
    });
    return;
  }

  const fileIdsForRequest = currentFiles
    .map((file) => String(file.id || "").trim())
    .filter(Boolean);
  let browsingForThisMessage = browsingEnabled;
  if (fileIdsForRequest.length > 0 && browsingForThisMessage) {
    browsingForThisMessage = false;
    showToast({
      title: "Browsing di-override",
      detail: "Karena ada file terlampir, request ini diproses sebagai RAG.",
      status: "info",
      timeoutMs: 3500,
    });
    pushActivity({
      title: "RAG prioritized",
      detail: "Browsing dinonaktifkan untuk request ini karena file terlampir.",
      status: "info",
    });
  }
  lastRequestMeta = {
    startedAt: performance.now(),
    message,
    browsing: browsingForThisMessage,
    files: currentFiles,
  };

  pushActivity({
    title: "Request sent",
    detail: message
      ? `Message: ${truncateText(message)}`
      : "Message: (file-only request)",
    status: "info",
  });
  if (browsingForThisMessage) {
    pushActivity({
      title: "Browsing enabled",
      detail: "Tooling for web browsing activated.",
      status: "warn",
    });
  }
  if (currentFiles.length > 0) {
    const fileNames = currentFiles.map((file) => file.name).join("\n");
    pushActivity({
      title: "Files attached",
      detail: fileNames,
      status: "info",
    });
  }
  const combinedInstructions = buildAssistantInstructions();
  if (combinedInstructions) {
    pushActivity({
      title: "Assistant instructions applied",
      detail: truncateText(combinedInstructions, 220),
      status: "info",
    });
  }
  if (activeAgent === "genesis") {
    const criticsCount = genesisConfig?.critics?.length || 1;
    pushActivity({
      title: "Multi-agent mode",
      detail: `Genesis enabled · critics ${criticsCount}`,
      status: "info",
    });
  }

  // Pass currentFiles to appendMessage
  if (message || currentFiles.length > 0) {
    appendMessage("user", message, {
      files: currentFiles,
      browsing: browsingForThisMessage,
    });
  }

  const previousTurns = [...history];
  input.value = "";
  input.focus();

  // Clear UI list
  uploadedFiles = [];
  fileDisplayArea.innerHTML = "";
  fileDisplayArea.hidden = true;

  try {
    setLoadingState(true);
    setActivityStatus("Working");
    showTypingIndicator();
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history: previousTurns,
        conversation_id: conversationId,
        files: currentFiles,
        file_ids: fileIdsForRequest,
        use_browsing: browsingForThisMessage,
        assistant_instructions: combinedInstructions,
        agent: activeAgent || "default",
        include_trace: thinkingTraceEnabled,
        genesis_config: activeAgent === "genesis" ? genesisConfig : undefined,
      }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Terjadi kesalahan.");
    }

    hideTypingIndicator();
    const previousConversationId = conversationId;
    if (payload.conversation_id) {
      setConversationId(payload.conversation_id);
    }

    const reply = payload.reply?.trim() || "Model tidak memberikan jawaban.";
    const sources = payload.sources || [];
    appendMessage("model", reply, { sources, trace: payload.trace || null });
    history.push({ role: "user", text: message });
    history.push({ role: "model", text: reply });
    const elapsedMs = lastRequestMeta ? performance.now() - lastRequestMeta.startedAt : 0;
    const inputTokens = estimateTokens(message);
    const outputTokens = estimateTokens(reply);
    updateActivitySummary({
      inputTokens,
      outputTokens,
      totalTokens: inputTokens + outputTokens,
      estimated: true,
      latencyMs: elapsedMs,
    });
    setActivityStatus("Ready");
    pushActivity({
      title: "Response received",
      detail: `Latency ${formatDuration(elapsedMs)} · Sources ${sources.length}`,
      status: "success",
    });
    const executionMeta =
      payload &&
      payload.meta &&
      payload.meta.execution &&
      typeof payload.meta.execution === "object"
        ? payload.meta.execution
        : null;
    if (executionMeta) {
      const modeValue = String(executionMeta.mode || "unknown");
      const providerValue = String(executionMeta.provider || "unknown");
      const modelValue = String(executionMeta.model || "unknown");
      const requestedBrowsing = Boolean(executionMeta.requested_browsing);
      const effectiveBrowsing = Boolean(executionMeta.effective_browsing);
      pushActivity({
        title: "Inference runtime",
        detail:
          `Mode ${modeValue} · ${providerValue} / ${modelValue}\n` +
          `Browsing requested=${requestedBrowsing} effective=${effectiveBrowsing}`,
        status: "info",
      });

      const fallbackMeta =
        executionMeta.fallback && typeof executionMeta.fallback === "object"
          ? executionMeta.fallback
          : null;
      if (fallbackMeta) {
        const fromProvider = String(fallbackMeta.from_provider || "unknown");
        const fromModel = String(fallbackMeta.from_model || "unknown");
        const toProvider = String(fallbackMeta.to_provider || "unknown");
        const toModel = String(fallbackMeta.to_model || "unknown");
        pushActivity({
          title: "Model fallback",
          detail: `${fromProvider} / ${fromModel} -> ${toProvider} / ${toModel}`,
          status: "warn",
        });
      }
    }
    if (sources.length > 0) {
      const sourceLines = sources.map((source) => {
        const sourceType = source.type ? ` | ${source.type}` : "";
        return source.page
          ? `${source.file} (p.${source.page}${sourceType})`
          : `${source.file}${sourceType}`;
      });
      pushActivity({
        title: "Sources cited",
        detail: sourceLines.join("\n"),
        status: "info",
      });
    }
    // Keep the Observatory inspector synchronized with the actual server response.
    window.dispatchEvent(new CustomEvent("parexa:response", {
      detail: { sources, files: currentFiles, execution: executionMeta }
    }));
    if (payload.activity) {
      applyActivityPayload(payload.activity);
    }
    if (conversationId) {
      // appendMessage already rendered the current turn with citation chips.
      // Fetching history immediately replaces it with older unannotated records.
      await refreshConversationList(conversationId);
    } else if (previousConversationId) {
      await refreshConversationList(previousConversationId);
    }
  } catch (error) {
    hideTypingIndicator();
    appendMessage("model", error.message);
    setActivityStatus("Error", true);
    pushActivity({
      title: "Request failed",
      detail: error.message || "Terjadi kesalahan.",
      status: "error",
    });
  } finally {
    setLoadingState(false);
  }
});
