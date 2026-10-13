/* Parexa Observatory model selection. All provider IDs come from /api/models.
 * The browser never supplies API URLs or secrets to the backend.
 */
(() => {
  "use strict";

  const select = document.getElementById("ob-chat-model-select");
  const status = document.getElementById("ob-model-status");
  const privacy = document.getElementById("ob-model-privacy");
  const locality = document.getElementById("ob-model-locality");
  const buttons = [
    document.getElementById("ob-model-button"),
    document.getElementById("ob-composer-model"),
  ].filter(Boolean);
  const refresh = document.getElementById("ob-refresh-models");
  if (!select || !status) return;

  const storageKey = "parexa.observatory.chat-model.v1";
  let routes = [];
  window.parexaChatModelSelection = null;

  function describe(route) {
    return route.local ? "Local · " + route.provider : "Cloud · " + route.provider;
  }

  function setSelection(route, { save = false } = {}) {
    window.parexaChatModelSelection = route
      ? { provider: route.provider, model: route.model }
      : null;

    const modelState = document.getElementById("studio-model-state");
    if (modelState) {
      modelState.textContent = route ? describe(route) : "No model connected";
      modelState.dataset.state = route ? "available" : "unavailable";
    }
    if (route) {
      const short = route.model.length > 20 ? route.model.slice(0, 19) + "…" : route.model;
      buttons.forEach((button) => {
        button.textContent = short;
        button.title = describe(route) + " / " + route.model;
      });
      if (locality) locality.textContent = route.local ? "Local" : "Cloud";
      status.textContent = (route.local ? "Running on your model server" : "Cloud API selected")
        + " · " + route.model;
      if (privacy) {
        privacy.textContent = route.local
          ? "Chat prompts go to your configured local model server. Embeddings and web search are configured separately."
          : "Cloud model selected: chat requests will be sent to the configured external provider. Review your data before sending.";
      }
    } else {
      buttons.forEach((button) => {
        button.textContent = "Choose model";
        button.title = "Choose an available chat model";
      });
      if (locality) locality.textContent = "Unavailable";
      if (privacy) {
        privacy.textContent = "No local chat model is available. Start LM Studio or Ollama, load a chat model, then refresh.";
      }
    }

    if (save) {
      try {
        if (route) {
          localStorage.setItem(storageKey, JSON.stringify({
            provider: route.provider,
            model: route.model,
          }));
        } else {
          localStorage.removeItem(storageKey);
        }
      } catch {
        // No storage required for live selection.
      }
    }
  }

  function getSaved() {
    try {
      const parsed = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (parsed && typeof parsed.provider === "string" && typeof parsed.model === "string") {
        return parsed;
      }
    } catch {
      // Ignore corrupt or inaccessible stored selection.
    }
    return null;
  }

  function openModelPicker() {
    const tab = document.querySelector('[data-ob-tab="context"]');
    const shell = document.querySelector(".app-shell");
    const toggle = document.getElementById("ob-inspector-toggle");
    if (!shell?.classList.contains("ob-inspector-open")) {
      toggle?.click();
    }
    tab?.click();
    select.focus();
  }

  buttons.forEach((button) => button.addEventListener("click", openModelPicker));

  select.addEventListener("change", () => {
    const index = Number(select.value);
    const route = Number.isInteger(index) && index >= 0 ? routes[index] : undefined;
    setSelection(route || null, { save: true });
    if (!route) status.textContent = "Select an available model to continue.";
  });

  async function loadModels() {
    select.disabled = true;
    status.textContent = "Discovering LM Studio and Ollama models…";
    if (refresh) refresh.disabled = true;
    try {
      const response = await fetch("/api/models", { cache: "no-store" });
      if (!response.ok) throw new Error("Model discovery API is unavailable.");
      const data = await response.json();
      routes = [];
      select.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "-1";
      placeholder.textContent = "Select a chat model";
      select.appendChild(placeholder);

      const providers = Array.isArray(data.providers) ? data.providers : [];
      for (const provider of providers) {
        const group = document.createElement("optgroup");
        group.label = String(provider.label || provider.id || "Model") +
          (provider.local ? " · Local" : " · Cloud");
        for (const model of Array.isArray(provider.models) ? provider.models : []) {
          if (!model || typeof model.id !== "string") continue;
          const option = document.createElement("option");
          option.value = String(routes.length);
          option.textContent = model.id;
          routes.push({
            provider: String(provider.id),
            model: model.id,
            local: Boolean(provider.local),
          });
          group.appendChild(option);
        }
        if (group.children.length) select.appendChild(group);
      }

      const saved = getSaved();
      const defaultRoute = data.default || {};
      let index = routes.findIndex((route) => saved &&
        route.provider === saved.provider && route.model === saved.model);
      if (index === -1) {
        index = routes.findIndex((route) =>
          route.provider === defaultRoute.provider && route.model === defaultRoute.model
        );
      }
      // Crucially, a missing local default must never choose a cloud model.
      select.value = index >= 0 ? String(index) : "-1";
      setSelection(index >= 0 ? routes[index] : null);
      select.disabled = routes.length === 0;

      if (index < 0) {
        const local = providers.filter((provider) => provider.local);
        const configured = local.find((provider) => provider.id === defaultRoute.provider);
        status.textContent = configured?.error
          ? configured.error
          : "No default model is available. Start a local server or select a configured provider.";
      }
    } catch {
      routes = [];
      select.replaceChildren();
      const option = document.createElement("option");
      option.value = "-1";
      option.textContent = "Model discovery unavailable";
      select.appendChild(option);
      select.disabled = true;
      setSelection(null);
      status.textContent = "Model discovery failed. Refresh after starting the backend.";
    } finally {
      if (refresh) refresh.disabled = false;
    }
  }

  refresh?.addEventListener("click", loadModels);
  loadModels();
})();
