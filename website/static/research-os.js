/* Parexa Research OS. Progressive frontend; all displayed records come from the local API. */
(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  const all = selector => Array.from(document.querySelectorAll(selector));
  const TYPES = ["projects", "documents", "notes", "experiments", "evidence", "tasks"];
  const LABELS = {
    overview:"OBSERVATORY", projects:"PROJECTS", library:"SOURCE VAULT",
    experiments:"EXPERIMENTS", evidence:"EVIDENCE LEDGER", notes:"NOTEBOOK",
    tasks:"RESEARCH QUEUE", system:"SYSTEMS & STORAGE"
  };
  const state = { view:"overview", scope:"", data:{}, overview:null, system:null };
  let editorKind = "";
  let editorId = "";
  let toastTimer;
  let searchTimer;
  let searchRevision = 0;
  let requestRevision = 0;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, char =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const short = (value, count=155) => {
    const s = String(value || "");
    return s.length > count ? s.slice(0,count) + "…" : s;
  };
  const bytes = value => {
    const number = Math.max(0,Number(value) || 0);
    if (number < 1024) return number + " B";
    const base = Math.floor(Math.log(number) / Math.log(1024));
    return (number / (1024 ** base)).toFixed(base > 1 ? 2 : 1) +
      " " + ["B","KiB","MiB","GiB","TiB"][Math.min(base,4)];
  };
  const date = value => value ? new Date(value).toLocaleDateString(undefined, {year:"numeric",month:"short",day:"numeric"}) : "—";
  const empty = message => '<div class="rx-empty">' + esc(message) + '</div>';
  const pill = (label, ok=false, warning=false) =>
    '<span class="rx-pill' + (ok ? " is-ok" : warning ? " is-warn" : "") + '">' + esc(label) + '</span>';
  const actions = (kind,id,deletable=true) =>
    '<div class="rx-record-actions"><button class="rx-record-action" type="button" data-edit="' + kind +
    '" data-id="' + esc(id) + '">Edit</button>' +
    (deletable ? '<button class="rx-record-action rx-record-action-danger" type="button" data-remove="' +
    kind + '" data-id="' + esc(id) + '">Remove</button>' : "") + '</div>';

  async function api(path, options={}) {
    const response = await fetch(path, { cache:"no-store", ...options });
    let data;
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) throw new Error(data.error || "Request failed (" + response.status + ")");
    return data;
  }
  function toast(message, error=false) {
    const element = byId("rx-toast");
    element.textContent = message;
    element.classList.toggle("is-error",error);
    element.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { element.hidden = true; }, 5200);
  }
  function setHtml(id, value) {
    const element = byId(id);
    if (element) element.innerHTML = value;
  }
  function scoped(path) {
    return path + (state.scope ? "?project_id=" + encodeURIComponent(state.scope) : "");
  }
  function collection(kind) { return state.data[kind] || []; }

  async function refresh() {
    const revision = ++requestRevision;
    byId("rx-footer-status").textContent = "Synchronizing research records…";
    try {
      const paths = ["/api/research/projects", scoped("/api/research/overview")].concat(
        TYPES.slice(1).map(kind => scoped("/api/research/" + kind))
      );
      const responses = await Promise.all(paths.map(path => api(path)));
      if (revision !== requestRevision) return;
      state.data.projects = responses[0].items;
      state.overview = responses[1];
      TYPES.slice(1).forEach((kind,index) => { state.data[kind] = responses[index+2].items; });
      syncScope();
      render();
      byId("rx-footer-status").textContent = "Vault connected · local records synchronized";
    } catch (err) {
      byId("rx-footer-status").textContent = "Vault unavailable";
      toast("Research vault could not load: " + err.message,true);
    }
  }

  function syncScope() {
    const select = byId("rx-scope");
    if (state.scope && !collection("projects").some(project => project.id === state.scope)) {
      state.scope = "";
    }
    select.replaceChildren();
    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "All research projects";
    select.append(allOption);
    collection("projects").forEach(project => {
      const option = document.createElement("option");
      option.value = project.id;
      option.textContent = project.title;
      select.append(option);
    });
    select.value = state.scope;
  }
  function setScope(id) {
    state.scope = id || "";
    try { localStorage.setItem("parexa.research.scope",state.scope); } catch {}
    byId("rx-scope").value = state.scope;
    refresh();
  }
  function navigate(view) {
    if (!(view in LABELS)) return;
    state.view = view;
    all("[data-screen]").forEach(screen => { screen.hidden = screen.dataset.screen !== view; });
    all(".rx-nav-item").forEach(item => {
      item.classList.toggle("is-active", item.dataset.view === view);
      if (item.dataset.view === view) item.setAttribute("aria-current","page");
      else item.removeAttribute("aria-current");
    });
    byId("rx-path-label").textContent = LABELS[view];
    byId("rx-content").scrollTop = 0;
    closeMobileNav();
    if (view === "system") refreshSystem();
  }
  function render() {
    if (!state.overview) return;
    renderOverview();
    renderProjects();
    renderDocuments();
    renderExperiments();
    renderEvidence();
    renderNotes();
    renderTasks();
    if (state.view === "system") refreshSystem();
  }
  function renderOverview() {
    const o = state.overview || {counts:{},projects:[],documents:[],tasks:[]};
    const c = o.counts || {};
    const metrics = [
      ["PROJECTS",c.projects||0,"Research scopes"],
      ["SOURCE OBJECTS",c.documents||0,(c.indexed||0)+" RAG indexed"],
      ["EVIDENCE LINKS",c.evidence||0,"Source-linked claims"],
      ["OPEN TASKS",c.open_tasks||0,bytes(c.storage_bytes||0)+" preserved"],
    ];
    setHtml("rx-metrics",metrics.map(item =>
      '<article class="rx-metric"><span class="rx-metric-label">' + esc(item[0]) +
      '</span><div class="rx-metric-bottom"><strong class="rx-metric-number">' + esc(item[1]) +
      '</strong><span class="rx-metric-sub">' + esc(item[2]) + '</span></div></article>'
    ).join(""));
    setHtml("rx-home-projects",o.projects.length ? o.projects.map(project =>
      '<div class="rx-dash-item"><span class="rx-dash-badge">' + esc(project.title.charAt(0).toUpperCase()) +
      '</span><span class="rx-dash-copy"><strong>' + esc(project.title) +
      '</strong><small>Updated ' + esc(date(project.updated_at)) + '</small></span>' +
      pill(project.status,project.status==="active") + '</div>'
    ).join("") : empty("No projects yet. Create one to organize a research question."));
    setHtml("rx-home-tasks",o.tasks.length ? o.tasks.map(task =>
      '<div class="rx-dash-item"><span class="rx-dash-badge">✓</span><span class="rx-dash-copy"><strong>' +
      esc(task.title) + '</strong><small>' + esc(task.description || "No description") +
      '</small></span>' + pill(task.status,task.status==="done") + '</div>'
    ).join("") : empty("Your next experiment, question, or reading task belongs here."));
    setHtml("rx-home-documents",o.documents.length ? o.documents.map(doc =>
      '<div class="rx-dash-item"><span class="rx-dash-badge">▤</span><span class="rx-dash-copy"><strong>' +
      esc(doc.name) + '</strong><small>' + esc(bytes(doc.size_bytes)) +
      ' · SHA-256: ' + esc(doc.sha256.slice(0,12)) + '…</small></span>' +
      pill(doc.index_status,doc.index_status==="indexed",doc.index_status==="stored") + '</div>'
    ).join("") : empty("Upload documents to retain the original bytes, even when embeddings are offline."));
  }
  function renderProjects() {
    const projects = collection("projects").filter(project => !state.scope || project.id === state.scope);
    setHtml("rx-projects",projects.length ? projects.map(project =>
      '<article class="rx-card"><span class="rx-card-overline">RESEARCH / ' + esc(project.status.toUpperCase()) +
      '</span><h3>' + esc(project.title) + '</h3><p>' + esc(short(project.description || "A new space for a research question.",240)) +
      '</p><div class="rx-card-foot"><small>Created ' + esc(date(project.created_at)) +
      '</small><div class="rx-record-actions"><button class="rx-record-action" data-scope="' + esc(project.id) +
      '" type="button">Open</button><button class="rx-record-action" data-edit="projects" data-id="' +
      esc(project.id) + '" type="button">Edit</button></div></div></article>'
    ).join("") : empty("No matching project in this scope. Create your first project."));
  }
  function renderDocuments() {
    const docs = collection("documents");
    const counts = state.overview.counts;
    setHtml("rx-library-summary",[
      ["ARCHIVED SOURCES",docs.length],
      ["INDEXED FOR RAG",counts.indexed||0],
      ["PHYSICAL OBJECT BYTES",bytes(counts.storage_bytes||0)]
    ].map(item => '<div class="rx-vault-item"><small>' + esc(item[0]) + '</small><strong>' +
       esc(item[1]) + '</strong></div>').join(""));
    if (!docs.length) { setHtml("rx-documents",empty("The vault is empty. Archive a PDF, Markdown or TXT source to begin.")); return; }
    setHtml("rx-documents",'<table class="rx-table"><thead><tr><th>SOURCE DOCUMENT</th><th>INDEX</th><th>SIZE</th><th>SHA-256</th><th>INTEGRITY / ACTION</th></tr></thead><tbody>' +
      docs.map(doc =>
        '<tr><td><strong>' + esc(doc.name) + '</strong><small>' + esc(date(doc.created_at)) +
        '</small></td><td>' + pill(doc.index_status,doc.index_status==="indexed",doc.index_status==="stored") +
        '</td><td>' + esc(bytes(doc.size_bytes)) + '</td><td class="rx-hash" title="' + esc(doc.sha256) +
        '">' + esc(doc.sha256.slice(0,18)) + '…</td><td><div class="rx-record-actions"><button type="button" class="rx-record-action" data-verify="' +
        esc(doc.id) + '">Verify</button><a class="rx-record-action" href="/api/research/documents/' +
        encodeURIComponent(doc.id) + '/download">Download ↗</a></div></td></tr>'
      ).join("") + '</tbody></table>');
  }
  function renderExperiments() {
    const list = collection("experiments");
    setHtml("rx-experiments",list.length ? list.map(exp =>
      '<article class="rx-list-row"><div class="rx-row-main"><span class="rx-row-kicker">EXPERIMENT / ' +
      esc(exp.id.slice(0,8)) + '</span><h3>' + esc(exp.title) +
      '</h3><p><strong>Hypothesis:</strong> ' + esc(short(exp.hypothesis || "Not stated",500)) +
      '</p><p><strong>Method:</strong> ' + esc(short(exp.method || "Not recorded",400)) +
      '</p>' + (exp.result ? '<p><strong>Outcome:</strong> ' + esc(short(exp.result,400)) + '</p>' : "") +
      '<div class="rx-row-meta">' + pill(exp.status,exp.status==="completed",exp.status==="planned") +
      pill(date(exp.updated_at)) + '</div></div>' + actions("experiments",exp.id) + '</article>'
    ).join("") : empty("No experiments recorded. Start with a hypothesis and document the method before running anything."));
  }
  function renderEvidence() {
    const list = collection("evidence");
    const docs = new Map(collection("documents").map(doc => [doc.id,doc]));
    setHtml("rx-evidence",list.length ? list.map(evidence => {
      const document = docs.get(evidence.document_id);
      return '<article class="rx-list-row"><div class="rx-row-main"><span class="rx-row-kicker">EVIDENCE / ' +
      esc(evidence.confidence.toUpperCase()) + ' CONFIDENCE</span><h3>' + esc(evidence.claim) +
      '</h3><p>“' + esc(short(evidence.quote,1200)) + '”</p><div class="rx-row-meta">' +
      pill(document?.name || "Source record",Boolean(document)) +
      pill(evidence.page_label ? "Page " + evidence.page_label : "Page unspecified") +
      pill(evidence.confidence,evidence.confidence==="high",evidence.confidence==="unreviewed") +
      '</div></div>' + actions("evidence",evidence.id) + '</article>';
    }).join("") : empty("No evidence yet. Each claim must cite a source already in your vault."));
  }
  function renderNotes() {
    const list = collection("notes");
    setHtml("rx-notes",list.length ? list.map(note =>
      '<article class="rx-card"><span class="rx-card-overline">NOTEBOOK / ' + esc(date(note.updated_at)) +
      '</span><h3>' + esc(note.title) + '</h3><p>' + esc(short(note.content || "Empty note",350)) +
      '</p><div class="rx-card-foot"><small>Saved on local disk</small>' +
      actions("notes",note.id) + '</div></article>'
    ).join("") : empty("Your research notebook is empty. Notes saved here persist on the Parexa server."));
  }
  function renderTasks() {
    const list = collection("tasks");
    setHtml("rx-tasks",list.length ? list.map(task =>
      '<article class="rx-list-row"><div class="rx-row-main"><span class="rx-row-kicker">TASK / ' +
      esc(task.priority.toUpperCase()) + ' PRIORITY</span><h3>' + esc(task.title) +
      '</h3><p>' + esc(task.description || "No details yet.") + '</p>' +
      '<div class="rx-row-meta">' + pill(task.status,task.status==="done") +
      pill(date(task.updated_at)) + '</div></div><div class="rx-record-actions">' +
      '<button class="rx-record-action" type="button" data-toggle-task="' + esc(task.id) + '">' +
      (task.status === "done" ? "Reopen" : "Complete") + '</button>' +
      '<button class="rx-record-action" type="button" data-edit="tasks" data-id="' + esc(task.id) +
      '">Edit</button><button class="rx-record-action rx-record-action-danger" type="button" data-remove="tasks" data-id="' +
      esc(task.id) + '">Remove</button></div></article>'
    ).join("") : empty("A clear research question is easier to answer when the work is divided into tasks."));
  }

  function kv(label,value) { return '<div class="rx-kv"><span>' + esc(label) + '</span><strong>' + esc(value) + '</strong></div>'; }
  async function refreshSystem() {
    setHtml("rx-system",empty("Checking storage, inference discovery and embedding status..."));
    const requests = await Promise.allSettled([
      api("/api/research/system"),api("/api/models"),api("/api/health/embedding")
    ]);
    if (state.view !== "system") return;
    const system = requests[0].status === "fulfilled" ? requests[0].value : null;
    const models = requests[1].status === "fulfilled" ? requests[1].value : null;
    const embed = requests[2].status === "fulfilled" ? requests[2].value : null;
    const storage = system?.storage || {};
    const capabilities = system?.capabilities || {};
    const providers = models?.providers || [];
    const providerRows = providers.length ? providers.map(p =>
      kv(p.label || p.id, p.local ? (p.online ? p.models.length + " model(s) detected" : "Not detected") : "Configured, not health-checked")
    ).join("") : kv("Model discovery",models ? "No providers configured" : "Unavailable");
    setHtml("rx-system",
      '<article class="rx-system-card"><p class="rx-panel-kicker">DATA PLANE</p><h2>Original source vault</h2>' +
      kv("Preserved data",bytes(storage.documents_bytes)) +
      kv("Metadata database",bytes(storage.metadata_bytes)) +
      kv("Original documents",storage.documents ?? "Unknown") +
      kv("RAG indexed",storage.indexed_documents ?? "Unknown") +
      kv("Available disk",bytes(storage.free_bytes)) +
      kv("Integrity",storage.hash_algorithm || "Unknown") + '</article>' +
      '<article class="rx-system-card"><p class="rx-panel-kicker">INFERENCE PLANE</p><h2>Model runtimes</h2>' +
      providerRows + kv("Selected default",models?.default?.provider || system?.runtime?.chat_provider || "Unavailable") +
      kv("Embedding provider",embed?.provider || system?.runtime?.embedding_provider || "Unknown") +
      kv("Embedding health",embed ? (embed.enabled ? (embed.healthy ? "Healthy" : "Unavailable") : "Not actively monitored") : "Unknown") +
      '</article>' +
      '<article class="rx-system-card"><p class="rx-panel-kicker">RESEARCH CAPABILITIES</p><h2>System boundaries</h2>' +
      kv("Source integrity",capabilities.integrity_verification ? "SHA-256 verification" : "Not supported") +
      kv("RAG index",capabilities.retrieval || "Unknown") +
      kv("GPU telemetry",capabilities.gpu_telemetry ? "Enabled" : "Not implemented") +
      kv("Auto-reindex",capabilities.automated_reindex ? "Enabled" : "Not implemented") +
      kv("Full workspace backup",capabilities.workspace_backup ? "Enabled" : "Not implemented") +
      '</article>' +
      '<article class="rx-system-card"><p class="rx-panel-kicker">DATA BOUNDARIES</p><h2>Privacy & reliability</h2>' +
      '<p class="rx-system-note">Research metadata and archived source bytes remain on your configured Parexa data volume. ' +
      'External model or embedding providers may send content off-device when configured. ' +
      'A saved source is not automatically an indexed source. The local Flask server has no login system and must stay on loopback.</p>' +
      kv("Cloud model selection",system?.runtime?.cloud_model_selection_enabled ? "Opted in" : "Disabled") +
      '</article>');
  }

  function addField(root, name, label, type, value="", options=[]) {
    const wrapper = document.createElement("label");
    wrapper.className = "rx-form-field";
    const caption = document.createElement("span");
    caption.textContent = label;
    wrapper.append(caption);
    let control;
    if (type === "textarea") {
      control = document.createElement("textarea");
      control.rows = name === "content" ? 8 : 4;
    } else if (type === "select") {
      control = document.createElement("select");
      options.forEach(option => {
        const item = document.createElement("option");
        item.value = option[0];
        item.textContent = option[1];
        control.append(item);
      });
    } else {
      control = document.createElement("input");
      control.type = "text";
    }
    control.name = name;
    control.value = value ?? "";
    if (["title","claim","quote","document_id"].includes(name)) control.required = true;
    if (name === "title") control.maxLength = 200;
    wrapper.append(control);
    root.append(wrapper);
  }
  const resource = kind => kind === "project" ? "projects" : kind === "note" ? "notes" :
    kind === "experiment" ? "experiments" : kind === "task" ? "tasks" : kind === "evidence" ? "evidence" : kind;
  const projectOptions = () => [["","Unassigned / global"]].concat(
    collection("projects").map(project => [project.id,project.title])
  );
  function openEditor(kind, id="") {
    const collectionName = resource(kind);
    const record = id ? collection(collectionName).find(item => item.id === id) : null;
    if (id && !record) { toast("Record is no longer available in this scope.",true); return; }
    editorKind = collectionName;
    editorId = id;
    byId("rx-editor-title").textContent = (id ? "Edit " : "Create ") +
      ({projects:"research project",notes:"research note",experiments:"experiment",evidence:"evidence record",tasks:"task"}[collectionName] || "record");
    byId("rx-editor-description").textContent =
      collectionName === "evidence" ? "Use a preserved source and an exact supporting excerpt. Confidence is not AI-verified." :
      "Saved to the local research database. Content is not silently added to AI model context.";
    const fields = byId("rx-editor-fields");
    fields.replaceChildren();
    const value = key => record?.[key] ?? "";
    const project = () => addField(fields,"project_id","Research project","select",value("project_id") || state.scope,projectOptions());
    if (collectionName === "projects") {
      addField(fields,"title","Project name","text",value("title"));
      addField(fields,"description","Research objective","textarea",value("description"));
      if (id) addField(fields,"status","Status","select",value("status"),[
        ["active","Active"],["paused","Paused"],["archived","Archived"]]);
    } else if (collectionName === "notes") {
      addField(fields,"title","Note title","text",value("title"));
      addField(fields,"content","Research note","textarea",value("content"));
      project();
    } else if (collectionName === "experiments") {
      addField(fields,"title","Experiment title","text",value("title"));
      addField(fields,"hypothesis","Hypothesis","textarea",value("hypothesis"));
      addField(fields,"method","Method / setup","textarea",value("method"));
      addField(fields,"result","Measured result / outcome","textarea",value("result"));
      addField(fields,"status","Experiment status","select",value("status") || "planned",[
        ["planned","Planned"],["running","Running"],["completed","Completed"],["paused","Paused"]]);
      project();
    } else if (collectionName === "tasks") {
      addField(fields,"title","Task title","text",value("title"));
      addField(fields,"description","Details","textarea",value("description"));
      addField(fields,"priority","Priority","select",value("priority") || "normal",[
        ["low","Low"],["normal","Normal"],["high","High"]]);
      addField(fields,"status","Status","select",value("status") || "todo",[
        ["todo","To do"],["doing","In progress"],["done","Done"]]);
      project();
    } else if (collectionName === "evidence") {
      const docs = collection("documents");
      addField(fields,"document_id","Original source document","select",value("document_id"),[
        ["","Select a source document"]].concat(docs.map(doc => [doc.id,doc.name])));
      addField(fields,"claim","Claim supported by the source","textarea",value("claim"));
      addField(fields,"quote","Exact quotation / relevant text","textarea",value("quote"));
      addField(fields,"page_label","Page or section label","text",value("page_label"));
      addField(fields,"confidence","Researcher-reviewed confidence","select",value("confidence") || "unreviewed",[
        ["unreviewed","Unreviewed"],["low","Low"],["medium","Medium"],["high","High"]]);
    }
    const dialog = byId("rx-editor");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open","");
    fields.querySelector("input,textarea,select")?.focus();
  }
  async function saveEditor(event) {
    event.preventDefault();
    const form = byId("rx-editor-form");
    const payload = Object.fromEntries(new FormData(form).entries());
    if (editorKind === "evidence") {
      const source = collection("documents").find(doc => doc.id === payload.document_id);
      if (!source) { toast("Select a valid source document.",true); return; }
      payload.project_id = source.project_id;
    }
    if (editorKind === "projects" && !editorId) delete payload.status;
    const path = "/api/research/" + editorKind + (editorId ? "/" + encodeURIComponent(editorId) : "");
    try {
      await api(path,{method:editorId ? "PATCH" : "POST",
        headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      byId("rx-editor").close();
      toast("Research record saved to disk.");
      await refresh();
    } catch (error) { toast(error.message,true); }
  }
  async function deleteRecord(kind,id) {
    if (!window.confirm("Remove this research record? This action cannot be undone.")) return;
    try {
      await api("/api/research/" + kind + "/" + encodeURIComponent(id),{method:"DELETE"});
      await refresh();
      toast("Research record removed.");
    } catch (error) { toast(error.message,true); }
  }
  async function toggleTask(id) {
    const task = collection("tasks").find(item => item.id === id);
    if (!task) return;
    try {
      await api("/api/research/tasks/" + encodeURIComponent(id),{
        method:"PATCH",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({status:task.status === "done" ? "todo" : "done"})
      });
      await refresh();
    } catch (error) { toast(error.message,true); }
  }
  async function archiveFiles(files) {
    if (!files.length) return;
    let saved = 0;
    const errors = [];
    for (const file of files) {
      const body = new FormData();
      body.append("file",file);
      if (state.scope) body.append("project_id",state.scope);
      try {
        await api("/api/research/documents",{method:"POST",body});
        saved++;
      } catch (error) { errors.push(file.name + ": " + error.message); }
    }
    byId("rx-vault-file").value = "";
    await refresh();
    if (saved) toast(saved + " source(s) archived. Originals preserved; RAG indexing is separate.");
    if (errors.length) toast(errors.slice(0,3).join(" | "),true);
  }
  async function verifyDocument(id) {
    try {
      const result = await api("/api/research/documents/" + encodeURIComponent(id) + "/verify");
      toast(result.valid ? "SHA-256 verified: original bytes match the source record." :
        "Integrity check FAILED: source bytes are missing or changed.",!result.valid);
    } catch (error) { toast(error.message,true); }
  }
  async function importScratchpad() {
    let old = "";
    try { old = localStorage.getItem("parexa.observatory.notes.v1") || ""; } catch {}
    if (!old.trim()) { toast("No old browser scratchpad found. Nothing was changed."); return; }
    try {
      await api("/api/research/notes",{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({title:"Imported Observatory scratchpad",content:old,project_id:state.scope || null})});
      await refresh();
      toast("Scratchpad copied to the persistent notebook. Original browser note remains.");
    } catch (error) { toast(error.message,true); }
  }
  async function searchAll(query) {
    const box = byId("rx-search-results");
    if (query.length < 2) { box.hidden = true; return; }
    const revision = ++searchRevision;
    try {
      const results = await api("/api/research/search?q=" + encodeURIComponent(query));
      if (revision !== searchRevision) return;
      const map = {projects:"projects",documents:"library",notes:"notes",
        experiments:"experiments",evidence:"evidence"};
      const labels = {projects:"PROJECTS",documents:"SOURCES",notes:"NOTES",
        experiments:"EXPERIMENTS",evidence:"EVIDENCE"};
      let html = "";
      for (const [kind,view] of Object.entries(map)) {
        const items = results[kind] || [];
        if (!items.length) continue;
        html += '<div class="rx-search-group">' + labels[kind] + '</div>';
        html += items.slice(0,5).map(item =>
          '<button type="button" class="rx-search-hit" data-view="' + view + '">' +
          esc(short(item.title || item.name || item.claim,75)) + '<span>↗</span></button>'
        ).join("");
      }
      box.innerHTML = html || empty("No matching records in the local research database.");
      box.hidden = false;
    } catch { if (revision === searchRevision) box.hidden = true; }
  }
  function closeMobileNav() {
    document.querySelector(".rx-app")?.classList.remove("rx-mobile-open");
    byId("rx-mobile-backdrop").hidden = true;
  }
  document.addEventListener("click",event => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const view = target.closest("[data-view]");
    const create = target.closest("[data-new]");
    const edit = target.closest("[data-edit]");
    const remove = target.closest("[data-remove]");
    const verify = target.closest("[data-verify]");
    const scope = target.closest("[data-scope]");
    const task = target.closest("[data-toggle-task]");
    if (view) { navigate(view.dataset.view); byId("rx-search-results").hidden = true; }
    else if (create) {
      if (create.dataset.new === "document") byId("rx-vault-file").click();
      else openEditor(create.dataset.new);
    }
    else if (edit) openEditor(edit.dataset.edit,edit.dataset.id);
    else if (remove) deleteRecord(remove.dataset.remove,remove.dataset.id);
    else if (verify) verifyDocument(verify.dataset.verify);
    else if (scope) { navigate("overview"); setScope(scope.dataset.scope); }
    else if (task) toggleTask(task.dataset.toggleTask);
    else if (!target.closest(".rx-search-wrap")) byId("rx-search-results").hidden = true;
  });
  byId("rx-scope").addEventListener("change",event => setScope(event.target.value));
  byId("rx-vault-file").addEventListener("change",event => archiveFiles(Array.from(event.target.files)));
  byId("rx-editor-form").addEventListener("submit",saveEditor);
  byId("rx-dialog-close").addEventListener("click",() => byId("rx-editor").close());
  byId("rx-editor-cancel").addEventListener("click",() => byId("rx-editor").close());
  byId("rx-import-scratchpad").addEventListener("click",importScratchpad);
  byId("rx-refresh-system").addEventListener("click",refreshSystem);
  byId("rx-nav-toggle").addEventListener("click",() => {
    document.querySelector(".rx-app").classList.add("rx-mobile-open");
    byId("rx-mobile-backdrop").hidden = false;
  });
  byId("rx-mobile-backdrop").addEventListener("click",closeMobileNav);
  byId("rx-search").addEventListener("input",event => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => searchAll(event.target.value.trim()),190);
  });
  document.addEventListener("keydown",event => {
    if (event.key === "Escape") { closeMobileNav(); byId("rx-search-results").hidden = true; }
    const typing = ["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName);
    if (!typing && event.key === "/" || (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      byId("rx-search").focus();
    }
  });
  try { state.scope = localStorage.getItem("parexa.research.scope") || ""; } catch {}
  refresh();
})();
