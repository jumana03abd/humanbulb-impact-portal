const appState = {
  user: null,
  project: null,
  setupComponents: [],
  setupProgress: null,
  dashboard: null,
  analytics: null,
  grant: null,
  pendingUploadComponentId: null,
  isPreparingDashboard: false
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

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message = payload?.detail || payload || "Request failed.";
    const isAuthRoute = typeof url === "string" && url.startsWith("/api/auth/");
    if (response.status === 401 && !isAuthRoute) {
      if (!window.location.pathname.endsWith("/login.html") && !window.location.pathname.endsWith("login.html")) {
        window.location.href = "login.html";
      }
      throw new Error("Authentication required.");
    }
    throw new Error(message);
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

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  const precision = size >= 10 || unitIndex === 0 ? 0 : 1;
  return `${size.toFixed(precision)} ${units[unitIndex]}`;
}

function formatTimestamp(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getUploadMeta(file) {
  const parts = [];
  if (file.row_count !== null && file.row_count !== undefined) parts.push(`${file.row_count} rows parsed`);
  if (file.parsed_summary?.columns?.length) parts.push(`${file.parsed_summary.columns.length} columns`);
  parts.push(formatFileSize(Number(file.size_bytes)));
  const uploadedOn = formatTimestamp(file.created_at);
  if (uploadedOn) parts.push(uploadedOn);
  return parts.filter(Boolean).join(" · ");
}

function getUploadSchemaHint(file) {
  const columns = file.parsed_summary?.columns || [];
  if (!columns.length) return "";
  return columns.slice(0, 3).join(", ");
}

function applyProjectState(payload) {
  if (payload.user) appState.user = payload.user;
  if (payload.project) appState.project = payload.project;
  if (payload.setup_components) appState.setupComponents = payload.setup_components;
  if (payload.setup_progress) appState.setupProgress = payload.setup_progress;
}

async function requireSession() {
  if (appState.user) return appState.user;
  appState.user = await apiFetch("/api/auth/me");
  return appState.user;
}

async function loadCurrentProject() {
  const payload = await apiFetch("/api/projects/current");
  applyProjectState(payload);
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
  if (!appState.project) return null;
  const payload = await apiFetch("/api/projects/current/cohort-size", {
    method: "POST",
    body: JSON.stringify({ cohort_size: value })
  });
  applyProjectState(payload);
  return payload;
}

async function removeUpload(uploadId) {
  const payload = await apiFetch(`/api/projects/current/uploads/${uploadId}`, {
    method: "DELETE"
  });
  applyProjectState(payload);
  return payload;
}

function setDashboardButtonState(isReady) {
  ["setup-complete-button", "setup-next-button"].forEach((id) => {
    const button = document.getElementById(id);
    if (!button) return;
    button.disabled = !isReady;
    button.classList.toggle("is-disabled", !isReady);
  });
}

function renderSimpleSetup() {
  const components = appState.setupComponents || [];
  const progress = appState.setupProgress || {
    total_required: components.length + 1,
    completed_required: 0,
    total_uploads: 0,
    is_complete: false,
    missing_components: [],
    analysis_status: "draft"
  };
  const cohortSize = Number(appState.project?.cohort_size || 0);
  const autoLabel = document.getElementById("setup-auto-label");

  renderList("simple-upload-grid", components, (item) => `
    <div class="simple-upload-item ${item.uploads > 0 ? "connected" : ""}">
      <div class="simple-upload-copy">
        <strong>${escapeHtml(item.name)}</strong>
        <span>${escapeHtml(item.type)} · Multiple uploads allowed</span>
        ${item.files.length ? `
          <div class="upload-file-list">
            ${item.files.map((file) => `
              <div class="upload-file-item">
                <div class="upload-file-body">
                  <small class="upload-file-name">${escapeHtml(file.filename)}</small>
                  <small class="upload-file-meta">${escapeHtml(getUploadMeta(file))}</small>
                  ${getUploadSchemaHint(file) ? `<small class="upload-file-schema">${escapeHtml(getUploadSchemaHint(file))}</small>` : ""}
                </div>
                <button class="upload-file-remove button-reset" type="button" data-remove-upload-id="${file.id}" aria-label="Remove ${escapeHtml(file.filename)}">Remove</button>
              </div>
            `).join("")}
          </div>
        ` : ""}
      </div>
      <div class="simple-upload-meta">
        <button class="simple-upload-trigger button-reset ${item.uploads > 0 ? "connector-chip connected" : "upload-chip pending"}" type="button" data-setup-id="${item.id}">
          ${item.uploads > 0 ? `${item.uploads} uploaded` : "Upload"}
        </button>
      </div>
    </div>
  `);

  const progressLabel = document.getElementById("setup-progress-label");
  const progressNote = document.getElementById("setup-progress-note");
  const completeCard = document.getElementById("setup-complete-card");
  const cohortInput = document.getElementById("cohort-size-input");
  const completeCopy = document.getElementById("setup-complete-copy");

  if (cohortInput) cohortInput.value = cohortSize > 0 ? String(cohortSize) : "";
  if (progressLabel) progressLabel.textContent = `${progress.completed_required} of ${progress.total_required} connected`;
  if (progressNote) {
    progressNote.textContent = progress.is_complete
      ? (progress.analysis_status === "analyzed" ? "Dashboard is ready" : "Ready to generate dashboard")
      : progress.missing_components.length
        ? `Missing: ${progress.missing_components.slice(0, 2).join(", ")}${progress.missing_components.length > 2 ? ` +${progress.missing_components.length - 2} more` : ""}`
        : `${progress.total_uploads} total uploads added so far`;
  }
  if (autoLabel) {
    autoLabel.textContent = appState.isPreparingDashboard
      ? "Generating dashboard..."
      : progress.analysis_status === "analyzed"
        ? "Dashboard ready"
        : "Auto-generate dashboard when complete";
  }
  if (completeCard) completeCard.hidden = !progress.is_complete;
  if (completeCopy) {
    completeCopy.textContent = progress.analysis_status === "analyzed"
      ? "The Impact Dashboard is ready to review."
      : "The portal is ready to generate the Impact Dashboard from the uploaded files.";
  }
  setDashboardButtonState(progress.is_complete);
}

async function prepareDashboardAndContinue(forceMessage = false) {
  const progress = appState.setupProgress;
  if (!progress?.is_complete) {
    if (forceMessage) {
      setMessage("setup-upload-message", "Finish the cohort size entry and the remaining uploads before continuing.", true);
    }
    return;
  }

  if (progress.analysis_status === "analyzed") {
    window.location.href = "dashboard.html";
    return;
  }

  if (appState.isPreparingDashboard) return;
  appState.isPreparingDashboard = true;
  renderSimpleSetup();
  setMessage("setup-upload-message", "Everything is connected. Generating the Impact Dashboard...");

  try {
    await apiFetch("/api/projects/current/analyze", { method: "POST", body: "{}" });
    window.location.href = "dashboard.html";
  } catch (error) {
    appState.isPreparingDashboard = false;
    renderSimpleSetup();
    setMessage("setup-upload-message", error.message, true);
  }
}

function wireSetupNavigation() {
  ["setup-complete-button", "setup-next-button"].forEach((id) => {
    const button = document.getElementById(id);
    if (!button || button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await prepareDashboardAndContinue(true);
    });
  });
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
      if (appState.project) appState.project.cohort_size = normalized;
      renderSimpleSetup();
      window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        try {
          await saveCohortSize(normalized);
          renderSimpleSetup();
          wireSimpleSetup();
          if (appState.setupProgress?.is_complete) {
            await prepareDashboardAndContinue(false);
          }
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
        if (payload) applyProjectState(payload);
        renderSimpleSetup();
        wireSimpleSetup();
        setMessage("setup-upload-message", `${files.length} file${files.length > 1 ? "s were" : " was"} uploaded successfully.`);
        if (appState.setupProgress?.is_complete) {
          await prepareDashboardAndContinue(false);
        }
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

  document.querySelectorAll("[data-remove-upload-id]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const uploadId = button.dataset.removeUploadId;
      if (!uploadId) return;
      try {
        setMessage("setup-upload-message", "Removing file...");
        await removeUpload(uploadId);
        renderSimpleSetup();
        wireSimpleSetup();
        setMessage("setup-upload-message", "File removed.");
      } catch (error) {
        setMessage("setup-upload-message", error.message, true);
      }
    });
  });

  wireSetupNavigation();
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
  const emailStep = document.getElementById("email-step");
  const passwordStep = document.getElementById("password-step");
  const emailForm = document.getElementById("email-step-form");
  const passwordForm = document.getElementById("password-step-form");
  const emailInput = document.getElementById("staff-email");
  const selectedEmail = document.getElementById("selected-email");
  const backButton = document.getElementById("back-to-email-button");
  const submitButton = document.getElementById("password-submit-button");
  const passwordInput = document.getElementById("auth-password");
  const confirmPasswordInput = document.getElementById("auth-confirm-password");

  const params = new URLSearchParams(window.location.search);

  function showStep(step, email = "") {
    const normalizedEmail = email.trim().toLowerCase();
    const isPasswordStep = step === "password";
    if (emailStep) emailStep.hidden = isPasswordStep;
    if (passwordStep) passwordStep.hidden = !isPasswordStep;
    if (emailInput && normalizedEmail) emailInput.value = normalizedEmail;
    if (selectedEmail) selectedEmail.textContent = normalizedEmail;
    if (submitButton) submitButton.textContent = "Enter Portal";

    if (!isPasswordStep) {
      if (passwordInput) passwordInput.value = "";
      if (confirmPasswordInput) confirmPasswordInput.value = "";
    }

    const nextParams = new URLSearchParams();
    if (isPasswordStep && normalizedEmail) {
      nextParams.set("step", "password");
      nextParams.set("email", normalizedEmail);
    }
    const nextQuery = nextParams.toString();
    const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
    setMessage("auth-message", "");
  }

  const initialStep = params.get("step") === "password" && params.get("email") ? "password" : "email";
  const initialEmail = params.get("email") || "";
  showStep(initialStep, initialEmail);

  emailForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const email = (emailInput?.value || "").trim().toLowerCase();
    if (!email) {
      setMessage("auth-message", "Enter your staff email to continue.", true);
      return;
    }
    showStep("password", email);
    passwordInput?.focus();
  });

  backButton?.addEventListener("click", () => {
    const email = selectedEmail?.textContent || emailInput?.value || "";
    showStep("email", email);
    emailInput?.focus();
  });

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const inputId = button.dataset.passwordToggle;
      const input = inputId ? document.getElementById(inputId) : null;
      if (!input) return;
      const shouldShow = input.type === "password";
      input.type = shouldShow ? "text" : "password";
      button.textContent = shouldShow ? "Hide" : "Show";
      button.setAttribute("aria-label", shouldShow ? "Hide password" : "Show password");
    });
  });

  passwordForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = (selectedEmail?.textContent || emailInput?.value || "").trim().toLowerCase();
    const password = passwordInput?.value || "";
    const confirmPassword = confirmPasswordInput?.value || "";

    if (!email) {
      showStep("email");
      setMessage("auth-message", "Enter your staff email to continue.", true);
      return;
    }

    if (password !== confirmPassword) {
      setMessage("auth-message", "Passwords do not match.", true);
      return;
    }

    try {
      setMessage("auth-message", "Checking your portal access...");
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      window.location.href = "admin.html";
      return;
    } catch (loginError) {
      const loginMessage = loginError?.message || "Unable to sign in.";
      if (loginMessage.includes("approved HUMANBULB staff")) {
        setMessage("auth-message", loginMessage, true);
        return;
      }
      if (loginMessage !== "Invalid email or password.") {
        setMessage("auth-message", loginMessage, true);
        return;
      }
    }

    try {
      setMessage("auth-message", "Creating your portal access...");
      await apiFetch("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: "" })
      });
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      window.location.href = "admin.html";
    } catch (signupError) {
      const signupMessage = signupError?.message || "Unable to create account.";
      if (signupMessage.toLowerCase().includes("already") || signupMessage.toLowerCase().includes("registered")) {
        setMessage("auth-message", "That password did not match this staff account. Try the password already set for this email.", true);
        return;
      }
      if (signupMessage === "Invalid email or password.") {
        setMessage("auth-message", "That password did not match this staff account. Try the password already set for this email.", true);
        return;
      }
      setMessage("auth-message", signupMessage, true);
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
