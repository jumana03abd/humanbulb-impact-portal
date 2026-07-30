const appState = {
  user: null,
  project: null,
  setupComponents: [],
  dashboard: null,
  analytics: null,
  grant: null,
  pendingUploadComponentId: null
};

const COMPONENT_ACCEPT = {
  pre: ".csv,.xlsx",
  weekly: ".csv,.xlsx",
  post: ".csv,.xlsx",
  deliverables: ".csv,.xlsx",
  "resume-linkedin": ".csv,.xlsx",
  testimonials: ".csv,.xlsx",
  photos: ".png,.jpg,.jpeg,.webp,.pdf"
};

function metricMarkup(metric) {
  return `
    <article class="metric-card">
      <p class="eyebrow">${metric.label}</p>
      <h3>${metric.value}</h3>
      <p>${metric.note}</p>
    </article>
  `;
}

function renderList(targetId, items, template) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = items.map(template).join("");
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {})
    }
  });

  if (response.status === 401) {
    if (!window.location.pathname.endsWith("/login.html") && !window.location.pathname.endsWith("login.html")) {
      window.location.href = "login.html";
    }
    throw new Error("Authentication required.");
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(payload.detail || payload || "Request failed.");
  }
  return payload;
}

function setMessage(targetId, message, isError = false) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.textContent = message || "";
  el.classList.toggle("error", Boolean(isError));
  el.hidden = !message;
}

async function requireSession() {
  if (appState.user) return appState.user;
  appState.user = await apiFetch("/api/auth/me");
  return appState.user;
}

async function loadCurrentProject() {
  const payload = await apiFetch("/api/projects/current");
  appState.user = payload.user;
  appState.project = payload.project;
  appState.setupComponents = payload.setup_components;
  return payload;
}

function updateSidebarCopy() {
  const sidebarStrong = document.querySelector(".sidebar-card strong");
  const sidebarParagraph = document.querySelector(".sidebar-card p:last-child");
  if (!appState.project || !sidebarStrong || !sidebarParagraph) return;

  if (document.body.dataset.page === "dashboard") {
    sidebarStrong.textContent = `${appState.project.cohort_year || "Current"} cohort`;
    sidebarParagraph.textContent = `${appState.project.cohort_size || 0} interns in the current organization project.`;
  }

  if (document.body.dataset.page === "analytics" && appState.analytics) {
    sidebarStrong.textContent = `${appState.analytics.matched_response_count} matched responses`;
    sidebarParagraph.textContent = "Week 1 and Week 8 survey comparisons only include participants with records in both uploads.";
  }
}

async function saveCohortSize(value) {
  if (!appState.project) return;
  await apiFetch("/api/projects/current/cohort-size", {
    method: "POST",
    body: JSON.stringify({ cohort_size: value })
  });
  appState.project.cohort_size = value;
}

function renderSimpleSetup() {
  const components = appState.setupComponents || [];
  const cohortSize = Number(appState.project?.cohort_size || 0);
  const hasCohortSize = cohortSize > 0;
  const connectedCount = components.filter((item) => item.uploads > 0).length;
  const totalCount = components.length + 1;
  const completedCount = connectedCount + (hasCohortSize ? 1 : 0);
  const totalUploads = components.reduce((sum, item) => sum + item.uploads, 0);

  renderList("simple-upload-grid", components, (item) => `
    <button class="simple-upload-item button-reset ${item.uploads > 0 ? "connected" : ""}" type="button" data-setup-id="${item.id}">
      <div class="simple-upload-copy">
        <strong>${item.name}</strong>
        <span>${item.type} · Multiple uploads allowed</span>
        ${item.files.length ? `
          <div class="upload-file-list">
            ${item.files.slice(0, 3).map((file) => `<small>${file}</small>`).join("")}
            ${item.files.length > 3 ? `<small>+${item.files.length - 3} more</small>` : ""}
          </div>
        ` : ""}
      </div>
      <div class="simple-upload-meta">
        <span class="${item.uploads > 0 ? "connector-chip connected" : "upload-chip pending"}">
          ${item.uploads > 0 ? `${item.uploads} uploaded` : "Upload"}
        </span>
      </div>
    </button>
  `);

  const progressLabel = document.getElementById("setup-progress-label");
  const progressNote = document.getElementById("setup-progress-note");
  const completeCard = document.getElementById("setup-complete-card");
  const cohortInput = document.getElementById("cohort-size-input");
  if (cohortInput) cohortInput.value = hasCohortSize ? String(cohortSize) : "";
  if (progressLabel) progressLabel.textContent = `${completedCount} of ${totalCount} connected`;
  if (progressNote) {
    progressNote.textContent = completedCount === totalCount
      ? "Ready to continue to the dashboard."
      : hasCohortSize
        ? `${cohortSize} interns entered · ${totalUploads} total uploads added so far`
        : `${totalUploads} total uploads added so far`;
  }
  if (completeCard) completeCard.hidden = completedCount !== totalCount;
  setMessage("setup-upload-message", "", false);
}

function wireSimpleSetup() {
  const cohortInput = document.getElementById("cohort-size-input");
  const fileInput = document.getElementById("workspace-file-input");
  if (cohortInput && !cohortInput.dataset.bound) {
    cohortInput.dataset.bound = "true";
    let timer = null;
    cohortInput.addEventListener("input", () => {
      const value = Number.parseInt(cohortInput.value, 10);
      const normalized = Number.isFinite(value) && value > 0 ? value : 0;
      appState.project.cohort_size = normalized;
      renderSimpleSetup();
      window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        try {
          await saveCohortSize(normalized);
        } catch (error) {
          setMessage("setup-upload-message", error.message, true);
        }
      }, 250);
    });
  }

  if (fileInput && !fileInput.dataset.bound) {
    fileInput.dataset.bound = "true";
    fileInput.addEventListener("change", async () => {
      const componentId = fileInput.dataset.setupTarget;
      const files = Array.from(fileInput.files || []);
      if (!componentId || !files.length) return;
      try {
        setMessage("setup-upload-message", `Uploading ${files.length} file${files.length > 1 ? "s" : ""}...`);
        let payload = null;
        for (const file of files) {
          const formData = new FormData();
          formData.append("component", componentId);
          formData.append("file", file);
          payload = await apiFetch("/api/projects/current/uploads", {
            method: "POST",
            body: formData
          });
        }
        if (payload) {
          appState.setupComponents = payload.setup_components;
        }
        renderSimpleSetup();
        wireSimpleSetup();
        setMessage("setup-upload-message", `${files.length} file${files.length > 1 ? "s" : ""} uploaded successfully.`);
      } catch (error) {
        setMessage("setup-upload-message", error.message, true);
      } finally {
        fileInput.value = "";
      }
    });
  }

  document.querySelectorAll("[data-setup-id]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const componentId = button.dataset.setupId;
      if (!fileInput || !componentId) return;
      appState.pendingUploadComponentId = componentId;
      fileInput.dataset.setupTarget = componentId;
      fileInput.accept = COMPONENT_ACCEPT[componentId] || "";
      fileInput.click();
    });
  });
}

async function renderAdminPage() {
  await requireSession();
  await loadCurrentProject();
  renderSimpleSetup();
  wireSimpleSetup();
}

async function renderDashboardPage() {
  await requireSession();
  await loadCurrentProject();
  const payload = await apiFetch("/api/projects/current/dashboard");
  appState.dashboard = payload;
  updateSidebarCopy();
  renderList("dashboard-metrics", payload.metrics, metricMarkup);
  renderList("grant-objectives-grid", payload.grantObjectives, (item) => `
    <article class="objective-card">
      <div class="objective-top">
        <p class="eyebrow">${item.title}</p>
        <span class="objective-status ${item.statusTone}">${item.status}</span>
      </div>
      <p class="objective-copy">${item.description}</p>
      <div class="objective-values">
        <div>
          <span>Target</span>
          <strong>${item.target}</strong>
        </div>
        <div>
          <span>Current</span>
          <strong>${item.actual}</strong>
        </div>
      </div>
    </article>
  `);
}

async function renderAnalyticsPage() {
  await requireSession();
  await loadCurrentProject();
  const payload = await apiFetch("/api/projects/current/analytics");
  appState.analytics = payload;
  updateSidebarCopy();
  renderGroupedHorizontalChart("before-after-chart", payload.beforeAfter, {
    max: 5,
    colors: ["#FCE68A", "#2F8F5B"],
    labels: ["Week 1", "Week 8"]
  });
  renderList("delta-list", payload.deltas, (item) => `
    <div class="delta-row">
      <div class="delta-copy">
        <strong>${item.label}</strong>
        <span>Increase from Week 1 baseline</span>
      </div>
      <span class="delta-value">+${item.delta}%</span>
    </div>
  `);
  renderStackedBars("distribution-chart", payload.distribution);

  const notes = document.querySelector(".check-list");
  if (notes) {
    notes.innerHTML = payload.analyst_notes.map((note) => `<li>${note}</li>`).join("");
  }
}

async function renderGrantPage() {
  await requireSession();
  await loadCurrentProject();
  const payload = await apiFetch("/api/projects/current/grant-summary");
  appState.grant = payload;
  renderList("grant-metrics", payload.metrics, (item) => `
    <div class="grant-metric">
      <strong>${item.value}</strong>
      <span>${item.label}</span>
    </div>
  `);
  renderList("grant-objective-list", payload.objectives, (item) => `
    <div class="grant-objective-row">
      <div>
        <strong>${item.title}</strong>
        <p>${item.description}</p>
      </div>
      <div class="grant-objective-values">
        <span>Target: ${item.target}</span>
        <strong>${item.actual}</strong>
      </div>
    </div>
  `);
  const executiveSummary = document.getElementById("grant-executive-summary");
  const quote = document.getElementById("grant-quote");
  const narrative = document.getElementById("grant-narrative");
  if (executiveSummary) executiveSummary.textContent = payload.executive_summary;
  if (quote) quote.textContent = `"${payload.quote}"`;
  if (narrative) narrative.textContent = payload.narrative;
  wireGrantExport();
}

function wireGrantExport() {
  const exportButton = document.getElementById("export-pdf-button");
  if (!exportButton || exportButton.dataset.bound) return;
  exportButton.dataset.bound = "true";
  exportButton.addEventListener("click", async (event) => {
    event.preventDefault();
    const original = exportButton.textContent;
    exportButton.textContent = "Generating PDF...";
    try {
      const payload = await apiFetch("/api/projects/current/grant-summary/pdf", { method: "POST", body: "{}" });
      window.location.href = payload.download_url;
      exportButton.textContent = "Export PDF";
    } catch (error) {
      exportButton.textContent = original;
      alert(error.message);
    }
  });
}

function wireLoginPage() {
  const loginForm = document.getElementById("login-form");
  const signupForm = document.getElementById("signup-form");
  const toggleSignupButton = document.getElementById("toggle-signup-button");
  const toggleLoginButton = document.getElementById("toggle-login-button");

  toggleSignupButton?.addEventListener("click", () => {
    loginForm.hidden = true;
    signupForm.hidden = false;
    setMessage("auth-message", "");
  });

  toggleLoginButton?.addEventListener("click", () => {
    signupForm.hidden = true;
    loginForm.hidden = false;
    setMessage("auth-message", "");
  });

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      setMessage("auth-message", "Signing in...");
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: document.getElementById("login-email").value,
          password: document.getElementById("login-password").value
        })
      });
      window.location.href = "admin.html";
    } catch (error) {
      setMessage("auth-message", error.message, true);
    }
  });

  signupForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      setMessage("auth-message", "Creating account...");
      await apiFetch("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          email: document.getElementById("signup-email").value,
          password: document.getElementById("signup-password").value,
          full_name: document.getElementById("signup-name").value,
          organization_name: document.getElementById("signup-organization").value
        })
      });
      window.location.href = "admin.html";
    } catch (error) {
      setMessage("auth-message", error.message, true);
    }
  });
}

function renderGroupedHorizontalChart(targetId, items, options) {
  const el = document.getElementById(targetId);
  if (!el) return;
  const width = 720;
  const rowHeight = 66;
  const height = Math.max(items.length, 1) * rowHeight + 40;
  const labelSpace = 270;
  const barWidth = width - labelSpace - 40;

  const rows = items.map((item, index) => {
    const y = 24 + index * rowHeight;
    const beforeW = (item.before / options.max) * barWidth;
    const afterW = (item.after / options.max) * barWidth;
    return `
      <text class="axis-label axis-label-large" x="8" y="${y + 20}">${item.label}</text>
      <rect x="${labelSpace}" y="${y}" width="${beforeW}" height="16" rx="8" fill="${options.colors[0]}"></rect>
      <rect x="${labelSpace}" y="${y + 22}" width="${afterW}" height="16" rx="8" fill="${options.colors[1]}"></rect>
      <text class="axis-label" x="${labelSpace + beforeW + 8}" y="${y + 12}">${item.before.toFixed(1)}</text>
      <text class="axis-label" x="${labelSpace + afterW + 8}" y="${y + 34}">${item.after.toFixed(1)}</text>
    `;
  }).join("");

  el.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Before and after comparison chart">
      <text class="axis-label" x="${labelSpace}" y="16">${options.labels[0]}</text>
      <text class="axis-label" x="${labelSpace}" y="38">${options.labels[1]}</text>
      ${rows}
    </svg>
  `;
}

function renderStackedBars(targetId, items) {
  const el = document.getElementById(targetId);
  if (!el) return;
  const width = 680;
  const height = 260;
  const padding = 24;
  const barWidth = 220;
  const gap = 110;
  const totals = {
    before: items.reduce((sum, item) => sum + item.before, 0) || 1,
    after: items.reduce((sum, item) => sum + item.after, 0) || 1
  };
  const colors = ["#FCE68A", "#BFE3C8", "#0F2747"];

  function buildStack(x, label, field) {
    let offset = 0;
    const rects = items.map((item, index) => {
      const widthPx = (item[field] / totals[field]) * barWidth;
      const rect = `<rect x="${x + offset}" y="96" width="${widthPx}" height="42" rx="14" fill="${colors[index]}"></rect>`;
      offset += widthPx;
      return rect;
    }).join("");

    return `
      <text class="axis-label axis-label-large" x="${x}" y="72">${label}</text>
      ${rects}
      <text class="axis-label" x="${x}" y="158">100% of response distribution</text>
    `;
  }

  const legend = items.map((item, index) => `
    <rect x="${padding}" y="${184 + index * 22}" width="14" height="14" rx="4" fill="${colors[index]}"></rect>
    <text class="axis-label axis-label-large" x="${padding + 24}" y="${195 + index * 22}">${item.label}</text>
  `).join("");

  el.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Confidence distribution stacked chart">
      ${buildStack(24, "Week 1", "before")}
      ${buildStack(24 + barWidth + gap, "Week 8", "after")}
      ${legend}
    </svg>
  `;
}

async function boot() {
  const page = document.body.dataset.page;
  try {
    if (page === "login") {
      wireLoginPage();
      return;
    }
    if (page === "admin") {
      await renderAdminPage();
      return;
    }
    if (page === "dashboard") {
      await renderDashboardPage();
      return;
    }
    if (page === "analytics") {
      await renderAnalyticsPage();
      return;
    }
    if (page === "grant") {
      await renderGrantPage();
    }
  } catch (error) {
    console.error(error);
  }
}

boot();
