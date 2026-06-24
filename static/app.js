const resources = {
  "user-profiles": {
    title: "用户档案",
    listTitle: "用户档案",
    primary: "display_name",
    summary: ["role", "preferences", "communication_style"],
    tags: ["role"],
    fields: [
      { name: "display_name", label: "名称", type: "text", required: true },
      { name: "role", label: "角色", type: "text" },
      { name: "preferences", label: "偏好", type: "textarea" },
      { name: "communication_style", label: "沟通风格", type: "textarea" },
      { name: "long_term_context", label: "长期上下文", type: "textarea" },
    ],
  },
  "project-profiles": {
    title: "项目档案",
    listTitle: "项目档案",
    primary: "name",
    summary: ["goal", "notes"],
    tags: ["status", "stack"],
    fields: [
      { name: "name", label: "项目名称", type: "text", required: true },
      { name: "goal", label: "目标", type: "textarea" },
      { name: "status", label: "状态", type: "text" },
      { name: "stack", label: "技术栈", type: "text" },
      { name: "notes", label: "备注", type: "textarea" },
    ],
  },
  "issue-progress": {
    title: "问题进度",
    listTitle: "问题进度",
    primary: "title",
    summary: ["current_step", "next_action", "notes"],
    tags: ["state", "priority"],
    fields: [
      { name: "project_id", label: "关联项目", type: "project" },
      { name: "title", label: "问题标题", type: "text", required: true },
      {
        name: "state",
        label: "状态",
        type: "select",
        options: ["active", "blocked", "review", "done", "closed"],
      },
      {
        name: "priority",
        label: "优先级",
        type: "select",
        options: ["low", "medium", "high", "urgent"],
      },
      { name: "current_step", label: "当前进度", type: "textarea" },
      { name: "next_action", label: "下一步", type: "textarea" },
      { name: "notes", label: "备注", type: "textarea" },
    ],
  },
  "error-records": {
    title: "错误记录",
    listTitle: "错误记录",
    primary: "title",
    summary: ["symptom", "root_cause", "fix"],
    tags: ["environment"],
    fields: [
      { name: "project_id", label: "关联项目", type: "project" },
      { name: "title", label: "错误标题", type: "text", required: true },
      { name: "environment", label: "环境", type: "text" },
      { name: "symptom", label: "现象", type: "textarea" },
      { name: "root_cause", label: "根因", type: "textarea" },
      { name: "fix", label: "修复", type: "textarea" },
      { name: "prevention", label: "预防", type: "textarea" },
    ],
  },
  "prompt-templates": {
    title: "Prompt 模板",
    listTitle: "Prompt 模板",
    primary: "title",
    summary: ["body", "notes"],
    tags: ["platform"],
    fields: [
      { name: "platform", label: "平台", type: "text", required: true },
      { name: "title", label: "模板名称", type: "text", required: true },
      { name: "body", label: "模板内容", type: "textarea" },
      { name: "notes", label: "备注", type: "textarea" },
    ],
  },
};

const labels = {
  "user-profiles": "用户档案",
  "project-profiles": "项目档案",
  "issue-progress": "问题进度",
  "error-records": "错误记录",
  "prompt-templates": "Prompt 模板",
};

const state = {
  currentView: "dashboard",
  activeResource: "user-profiles",
  data: {},
  summary: null,
};

const viewTitle = document.querySelector("#view-title");
const dashboardView = document.querySelector("#dashboard-view");
const resourceView = document.querySelector("#resource-view");
const packageView = document.querySelector("#package-view");
const resourceForm = document.querySelector("#resource-form");
const recordList = document.querySelector("#record-list");
const recordCount = document.querySelector("#record-count");
const listTitle = document.querySelector("#list-title");
const summaryGrid = document.querySelector("#summary-grid");
const moduleGrid = document.querySelector("#module-grid");
const packageProject = document.querySelector("#package-project");
const packagePlatform = document.querySelector("#package-platform");
const packageOutput = document.querySelector("#package-output");
const packagePreview = document.querySelector("#package-preview");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

async function refresh() {
  const keys = Object.keys(resources);
  const [summary, ...collections] = await Promise.all([
    api("/api/summary"),
    ...keys.map((key) => api(`/api/${key}`)),
  ]);
  state.summary = summary;
  keys.forEach((key, index) => {
    state.data[key] = collections[index];
  });
  render();
}

function setView(view) {
  state.currentView = view;
  if (resources[view]) {
    state.activeResource = view;
  }
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  render();
}

function render() {
  dashboardView.classList.toggle("active", state.currentView === "dashboard");
  resourceView.classList.toggle("active", Boolean(resources[state.currentView]));
  packageView.classList.toggle("active", state.currentView === "context-package");

  if (state.currentView === "dashboard") {
    viewTitle.textContent = "总览";
    renderDashboard();
  } else if (state.currentView === "context-package") {
    viewTitle.textContent = "上下文包";
    renderPackageControls();
  } else {
    viewTitle.textContent = resources[state.activeResource].title;
    renderResource(state.activeResource);
  }
}

function renderDashboard() {
  const counts = state.summary?.counts || {};
  const metrics = [
    ["用户档案", counts["user-profiles"] || 0],
    ["项目档案", counts["project-profiles"] || 0],
    ["进行中问题", state.summary?.active_issues || 0],
    ["错误记录", counts["error-records"] || 0],
    ["Prompt 模板", counts["prompt-templates"] || 0],
    ["上下文类型", Object.keys(resources).length],
  ];
  summaryGrid.innerHTML = metrics
    .map((metric) => `<div class="metric"><span>${metric[0]}</span><strong>${metric[1]}</strong></div>`)
    .join("");
  moduleGrid.innerHTML = [
    ["用户档案", counts["user-profiles"] || 0],
    ["项目档案", counts["project-profiles"] || 0],
    ["问题进度", counts["issue-progress"] || 0],
    ["错误记录", counts["error-records"] || 0],
    ["Prompt 模板", counts["prompt-templates"] || 0],
    ["上下文包", "MD / JSON"],
  ]
    .map((item) => `<div>${item[0]}<span>${item[1]}</span></div>`)
    .join("");
}

function renderResource(key) {
  const config = resources[key];
  const items = state.data[key] || [];
  listTitle.textContent = config.listTitle;
  recordCount.textContent = items.length;
  renderForm(key);
  renderRecords(key, items);
}

function renderForm(key, editingItem = null) {
  const config = resources[key];
  resourceForm.dataset.resource = key;
  resourceForm.dataset.editId = editingItem?.id || "";
  resourceForm.innerHTML = `<h3>${editingItem ? "编辑" : "新增"}${config.title}</h3>`;
  config.fields.forEach((field) => {
    resourceForm.appendChild(createField(field, editingItem?.[field.name] || ""));
  });
  const row = document.createElement("div");
  row.className = "button-row";
  row.innerHTML = `
    <button type="submit">${editingItem ? "保存" : "新增"}</button>
    <button class="secondary-btn" type="button" data-action="reset-form">清空</button>
  `;
  resourceForm.appendChild(row);
}

function createField(field, value) {
  const label = document.createElement("label");
  const text = document.createElement("span");
  text.textContent = field.label;
  label.appendChild(text);

  let control;
  if (field.type === "textarea") {
    control = document.createElement("textarea");
  } else if (field.type === "select") {
    control = document.createElement("select");
    field.options.forEach((option) => {
      control.appendChild(new Option(option, option));
    });
  } else if (field.type === "project") {
    control = document.createElement("select");
    control.appendChild(new Option("未关联", ""));
    (state.data["project-profiles"] || []).forEach((project) => {
      control.appendChild(new Option(project.name, project.id));
    });
  } else {
    control = document.createElement("input");
    control.type = field.type || "text";
  }

  control.name = field.name;
  control.required = Boolean(field.required);
  control.value = value ?? "";
  label.appendChild(control);
  return label;
}

function renderRecords(key, items) {
  const config = resources[key];
  if (!items.length) {
    recordList.innerHTML = `<div class="empty-state">暂无记录</div>`;
    return;
  }

  recordList.innerHTML = "";
  items.forEach((item) => {
    const record = document.createElement("article");
    record.className = "record";
    const summary = config.summary
      .map((field) => item[field])
      .filter(Boolean)
      .join("\n");
    const tags = [
      ...config.tags.map((field) => item[field]).filter(Boolean),
      projectLabel(item.project_id),
    ].filter(Boolean);

    record.innerHTML = `
      <h4>${escapeHtml(item[config.primary])}</h4>
      ${summary ? `<p>${escapeHtml(summary)}</p>` : ""}
      ${tags.length ? `<div class="meta-row">${tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      <div class="record-actions">
        <button class="secondary-btn" type="button" data-action="edit" data-id="${item.id}">编辑</button>
        <button class="danger-btn" type="button" data-action="delete" data-id="${item.id}">删除</button>
      </div>
    `;
    recordList.appendChild(record);
  });
}

function projectLabel(projectId) {
  if (!projectId) return "";
  const project = (state.data["project-profiles"] || []).find((item) => item.id === projectId);
  return project ? project.name : "";
}

function formPayload(form) {
  const data = new FormData(form);
  return Object.fromEntries(
    [...data.entries()].map(([key, value]) => {
      const normalized = value.trim();
      return [key, key === "project_id" && !normalized ? null : normalized];
    }),
  );
}

async function submitResourceForm(event) {
  event.preventDefault();
  const key = resourceForm.dataset.resource;
  const id = resourceForm.dataset.editId;
  const payload = formPayload(resourceForm);
  const method = id ? "PUT" : "POST";
  const path = id ? `/api/${key}/${id}` : `/api/${key}`;
  await api(path, { method, body: JSON.stringify(payload) });
  await refresh();
  renderForm(key);
}

async function handleRecordAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  const key = state.activeResource;
  if (action === "reset-form") {
    renderForm(key);
    return;
  }
  const item = (state.data[key] || []).find((record) => record.id === button.dataset.id);
  if (!item) return;
  if (action === "edit") {
    renderForm(key, item);
  }
  if (action === "delete") {
    await api(`/api/${key}/${item.id}`, { method: "DELETE" });
    await refresh();
  }
}

function renderPackageControls() {
  const currentProject = packageProject.value;
  const currentPlatform = packagePlatform.value;
  packageProject.innerHTML = "";
  packageProject.appendChild(new Option("全部项目", ""));
  (state.data["project-profiles"] || []).forEach((project) => {
    packageProject.appendChild(new Option(project.name, project.id));
  });
  packageProject.value = currentProject;

  const platforms = [...new Set((state.data["prompt-templates"] || []).map((template) => template.platform).filter(Boolean))];
  packagePlatform.innerHTML = "";
  packagePlatform.appendChild(new Option("全部平台", ""));
  platforms.forEach((platform) => packagePlatform.appendChild(new Option(platform, platform)));
  packagePlatform.value = currentPlatform;
}

function packageQuery() {
  const params = new URLSearchParams({ output: packageOutput.value });
  if (packageProject.value) params.set("project_id", packageProject.value);
  if (packagePlatform.value) params.set("platform", packagePlatform.value);
  return params.toString();
}

async function generatePackage() {
  const result = await api(`/api/context-package?${packageQuery()}`);
  packagePreview.value = typeof result === "string" ? result : JSON.stringify(result, null, 2);
}

function downloadPackage() {
  window.location.href = `/api/context-package/download?${packageQuery()}`;
}

async function copyPackage() {
  if (!packagePreview.value) {
    await generatePackage();
  }
  await navigator.clipboard.writeText(packagePreview.value);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.querySelector("#refresh-btn").addEventListener("click", refresh);
resourceForm.addEventListener("submit", submitResourceForm);
resourceForm.addEventListener("click", handleRecordAction);
recordList.addEventListener("click", handleRecordAction);
document.querySelector("#generate-package-btn").addEventListener("click", generatePackage);
document.querySelector("#download-package-btn").addEventListener("click", downloadPackage);
document.querySelector("#copy-package-btn").addEventListener("click", copyPackage);

refresh().catch((error) => {
  console.error(error);
  summaryGrid.innerHTML = `<div class="empty-state">服务未就绪</div>`;
});
