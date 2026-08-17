const appState = {
  user: null,
  project: null,
  setupComponents: [],
  setupProgress: null,
  dashboard: null,
  analytics: null,
  grant: null,
  pendingUploadComponentId: null,
  isPreparingDashboard: false,
  uploadErrors: {}
};

// File extensions allowed per admin workspace upload category.
const COMPONENT_ACCEPT = {
  pre: ".csv,.xlsx",
  weekly: ".csv,.xlsx",
  post: ".csv,.xlsx",
  deliverables: ".csv,.xlsx",
  "resume-linkedin": ".csv,.xlsx",
  testimonials: ".csv,.xlsx",
  photos: ".zip,.png,.jpg,.jpeg,.webp"
};

function metricMarkup(metric) {
  // Build one dashboard metric card from the API response payload.
  return `
    <article class="metric-card">
      <p class="eyebrow">${metric.label}</p>
      <h3>${metric.value}</h3>
      <p>${metric.note}</p>
    </article>
  `;
}

function renderList(targetId, items, template) {
  // Render a repeated list of cards/rows into a target container.
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = items.map(template).join("");
}

function renderChartEmptyState(targetId, title, message) {
  // Replace blank chart regions with a clear explanation when comparison data is not ready yet.
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = `
    <div class="chart-empty-state">
      <strong>${title}</strong>
      <p>${message}</p>
    </div>
  `;
}

function renderFeaturedPhotos(targetId, photos, emptyTitle, emptyMessage) {
  // Render a small featured-photo gallery or a clear empty state when no photos are uploaded yet.
  const el = document.getElementById(targetId);
  if (!el) return;
  if (!Array.isArray(photos) || !photos.length) {
    el.innerHTML = `
      <div class="chart-empty-state compact">
        <strong>${emptyTitle}</strong>
        <p>${emptyMessage}</p>
      </div>
    `;
    return;
  }

  el.innerHTML = photos.map((photo) => `
    <article class="photo-panel photo-panel-image">
      <img class="photo-panel-media" src="${encodeURI(photo.url)}" alt="${escapeHtml(photo.caption || photo.filename || 'Program photo')}" loading="lazy" />
      <span class="photo-panel-caption">${escapeHtml(photo.caption || photo.filename || 'Program photo')}</span>
    </article>
  `).join("");
}

async function apiFetch(url, options = {}) {
  // Handle API requests and normalize auth/error behavior.
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
  // Show inline success/error feedback without interrupting the current screen.
  const el = document.getElementById(targetId);
  if (!el) return;
  el.textContent = message || "";
  el.classList.toggle("error", Boolean(isError));
  el.hidden = !message;
}

function setComponentUploadError(componentId, message = "") {
  // Store a category-specific upload error for the setup workspace.
  if (!componentId) return;
  if (!message) {
    delete appState.uploadErrors[componentId];
    return;
  }
  appState.uploadErrors[componentId] = message;
}

function clearAllUploadErrors() {
  // Clear all category-specific upload errors after successful state refreshes.
  appState.uploadErrors = {};
}

function getUploadError(componentId) {
  // Read the current upload error for one setup category.
  return appState.uploadErrors[componentId] || "";
}

function escapeHtml(value) {
  // Escape user/file text before inserting it into template strings.
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatFileSize(bytes) {
  // Convert raw byte counts into readable file sizes for the upload UI.
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
  // Format upload timestamps into short, friendly labels.
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getUploadMeta(file) {
  // Build the compact upload summary shown beneath each uploaded filename.
  const parts = [];
  if (file.row_count !== null && file.row_count !== undefined) parts.push(`${file.row_count} rows parsed`);
  if (file.parsed_summary?.columns?.length) parts.push(`${file.parsed_summary.columns.length} columns`);
  parts.push(formatFileSize(Number(file.size_bytes)));
  const uploadedOn = formatTimestamp(file.created_at);
  if (uploadedOn) parts.push(uploadedOn);
  return parts.filter(Boolean).join(" · ");
}

function getUploadSchemaHint(file) {
  // Surface a few parsed column names so staff can confirm they uploaded the right sheet.
  const columns = file.parsed_summary?.columns || [];
  if (!columns.length) return "";
  return columns.slice(0, 3).join(", ");
}

function applyProjectState(payload) {
  // Keep the current workspace/project state in sync with every API response.
  if (payload.user) appState.user = payload.user;
  if (payload.project) appState.project = payload.project;
  if (payload.setup_components) appState.setupComponents = payload.setup_components;
  if (payload.setup_progress) appState.setupProgress = payload.setup_progress;
}

async function requireSession() {
  // Fetch the current staff session once and reuse it across the page lifecycle.
  if (appState.user) return appState.user;
  appState.user = await apiFetch("/api/auth/me");
  return appState.user;
}

async function loadCurrentProject() {
  // Load the project, uploads, and setup progress that power the admin workflow.
  const payload = await apiFetch("/api/projects/current");
  applyProjectState(payload);
  return payload;
}

async function signOut() {
  // End the current staff session and always return the browser to the login screen.
  try {
    await apiFetch("/api/auth/logout", {
      method: "POST",
      body: JSON.stringify({})
    });
  } finally {
    appState.user = null;
    appState.project = null;
    appState.setupComponents = [];
    appState.setupProgress = null;
    appState.dashboard = null;
    appState.analytics = null;
    appState.grant = null;
    window.location.replace("login.html");
  }
}

function wireSignOutButton() {
  // Connect the sidebar sign-out button to the existing logout endpoint.
  const button = document.getElementById("sign-out-button");
  if (!button || button.dataset.bound === "true") return;
  button.dataset.bound = "true";
  button.addEventListener("click", async () => {
    const originalLabel = button.textContent;
    button.textContent = "Signing out...";
    button.disabled = true;
    try {
      await signOut();
    } catch (error) {
      button.textContent = originalLabel;
      button.disabled = false;
      alert(error.message || "Unable to sign out.");
    }
  });
}

function updateSidebarCopy() {
  // Adjust sidebar context so each screen reflects the current project state.
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
  // Persist the cohort size entered by staff during setup.
  if (!appState.project) return null;
  const payload = await apiFetch("/api/projects/current/cohort-size", {
    method: "POST",
    body: JSON.stringify({ cohort_size: value })
  });
  applyProjectState(payload);
  return payload;
}

async function saveReportingPeriod(value) {
  // Persist the reporting period entered by staff during setup.
  if (!appState.project) return null;
  const payload = await apiFetch("/api/projects/current/reporting-period", {
    method: "POST",
    body: JSON.stringify({ reporting_period: value })
  });
  applyProjectState(payload);
  return payload;
}

async function removeUpload(uploadId) {
  // Remove a single uploaded file from the active project.
  const payload = await apiFetch(`/api/projects/current/uploads/${uploadId}`, {
    method: "DELETE"
  });
  applyProjectState(payload);
  return payload;
}

function setDashboardButtonState(isReady) {
  // Enable navigation only when all required setup sources are connected.
  ["setup-complete-button", "setup-next-button"].forEach((id) => {
    const button = document.getElementById(id);
    if (!button) return;
    button.disabled = !isReady;
    button.classList.toggle("is-disabled", !isReady);
  });
}

function renderSimpleSetup() {
  // Render the simplified upload-first admin workspace requested for the MVP.
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
  const reportingPeriod = String(appState.project?.reporting_period || "");
  const autoLabel = document.getElementById("setup-auto-label");

  renderList("simple-upload-grid", components, (item) => {
    const uploadError = getUploadError(item.id);
    return `
    <div class="simple-upload-item ${item.uploads > 0 ? "connected" : ""} ${uploadError ? "has-error" : ""}">
      <div class="simple-upload-copy">
        <strong>${escapeHtml(item.name)}</strong>
        <span>${escapeHtml(item.type)} · Multiple uploads allowed</span>
        ${uploadError ? `<p class="upload-error-text">${escapeHtml(uploadError)}</p>` : ""}
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
  `;
  });

  const progressLabel = document.getElementById("setup-progress-label");
  const progressNote = document.getElementById("setup-progress-note");
  const completeCard = document.getElementById("setup-complete-card");
  const cohortInput = document.getElementById("cohort-size-input");
  const reportingPeriodInput = document.getElementById("reporting-period-input");
  const completeCopy = document.getElementById("setup-complete-copy");

  if (cohortInput) cohortInput.value = cohortSize > 0 ? String(cohortSize) : "";
  if (reportingPeriodInput) reportingPeriodInput.value = reportingPeriod;
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
  // Generate quantitative and qualitative outputs only after the workspace is complete.
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
  // Move staff from setup into dashboard generation once the workspace is complete.
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
  // Attach all upload, remove, and cohort-size behaviors for the admin setup page.
  const cohortInput = document.getElementById("cohort-size-input");
  const reportingPeriodInput = document.getElementById("reporting-period-input");
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


  if (reportingPeriodInput && !reportingPeriodInput.dataset.bound) {
    reportingPeriodInput.dataset.bound = "true";
    let timer = null;
    reportingPeriodInput.addEventListener("input", () => {
      const normalized = reportingPeriodInput.value.trimStart().slice(0, 120);
      if (appState.project) appState.project.reporting_period = normalized;
      window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        try {
          await saveReportingPeriod(normalized.trim());
          renderSimpleSetup();
          wireSimpleSetup();
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
        setComponentUploadError(componentId, "");
        renderSimpleSetup();
        wireSimpleSetup();
        setMessage("setup-upload-message", `${files.length} file${files.length > 1 ? "s were" : " was"} uploaded successfully.`);
        if (appState.setupProgress?.is_complete) {
          await prepareDashboardAndContinue(false);
        }
      } catch (error) {
        const uploadErrorMessage = error.message || "Upload failed.";
        const componentName = appState.setupComponents.find((item) => item.id === componentId)?.name || "Upload";
        setComponentUploadError(componentId, uploadErrorMessage);
        renderSimpleSetup();
        wireSimpleSetup();
        setMessage("setup-upload-message", `${componentName} needs attention. Review the highlighted category below.`, true);
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
        clearAllUploadErrors();
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
  // Boot the setup workspace with the current organization project state.
  await requireSession();
  await loadCurrentProject();
  wireSignOutButton();
  renderSimpleSetup();
  wireSimpleSetup();
}

async function renderDashboardPage() {
  // Render the KPI-style impact dashboard using analyzed backend results.
  await requireSession();
  await loadCurrentProject();
  const payload = await apiFetch("/api/projects/current/dashboard");
  appState.dashboard = payload;
  updateSidebarCopy();
  wireSignOutButton();
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
  renderFeaturedPhotos(
    "dashboard-featured-photos",
    payload.featuredPhotos,
    "Awaiting photo upload",
    "Upload individual images or a ZIP of the program photo folder to feature visuals here automatically."
  );
}

async function renderAnalyticsPage() {
  // Render the before/after comparison page and response distribution charts.
  await requireSession();
  await loadCurrentProject();
  wireSignOutButton();
  const payload = await apiFetch("/api/projects/current/analytics");
  appState.analytics = payload;
  updateSidebarCopy();
  renderGroupedHorizontalChart("before-after-chart", payload.beforeAfter, {
    max: 5,
    colors: ["#FCE68A", "#2F8F5B"],
    labels: ["Week 1", "Week 8"]
  });
  const deltaList = document.getElementById("delta-list");
  if (deltaList) {
    deltaList.innerHTML = payload.deltas.length
      ? payload.deltas.map((item) => `
        <div class="delta-row">
          <div class="delta-copy">
            <strong>${item.label}</strong>
            <span>Percent change from Week 1 baseline</span>
          </div>
          <span class="delta-value">+${item.delta}%</span>
        </div>
      `).join("")
      : `
        <div class="chart-empty-state compact">
          <strong>Awaiting Week 8 post-survey upload</strong>
          <p>Improvement percentages will appear here after the post-survey is uploaded and matched to Week 1 participant records.</p>
        </div>
      `;
  }
  renderStackedBars("distribution-chart", payload.distribution);

  const notes = document.querySelector(".check-list");
  if (notes) {
    notes.innerHTML = payload.analyst_notes.map((note) => `<li>${note}</li>`).join("");
  }
}

async function renderGrantPage() {
  // Render the grant-summary screen that previews the eventual exported PDF.
  await requireSession();
  await loadCurrentProject();
  wireSignOutButton();
  const payload = await apiFetch("/api/projects/current/grant-summary");
  appState.grant = payload;
  const internsServedMetric = Array.isArray(payload.metrics)
    ? payload.metrics.find((item) => String(item.label || "").toLowerCase().includes("interns served"))
    : null;
  const deliverablesMetric = Array.isArray(payload.metrics)
    ? payload.metrics.find((item) => String(item.label || "").toLowerCase().includes("deliverables"))
    : null;
  const materialsObjective = Array.isArray(payload.objectives)
    ? payload.objectives.find((item) => String(item.title || "").toLowerCase().includes("career materials"))
    : null;
  const cleanTechObjective = Array.isArray(payload.objectives)
    ? payload.objectives.find((item) => String(item.title || "").toLowerCase().includes("clean tech awareness"))
    : null;
  const workplaceObjective = Array.isArray(payload.objectives)
    ? payload.objectives.find((item) => String(item.title || "").toLowerCase().includes("workplace readiness"))
    : null;
  const projectSummaryText = [
    "Green Careers Launchpad combines career exposure, workplace readiness development, and project-based learning for interns exploring green career pathways.",
    internsServedMetric?.value ? `The current reporting set reflects ${internsServedMetric.value} interns served` : "",
    deliverablesMetric?.value ? `${deliverablesMetric.value} deliverables logged` : "",
    materialsObjective?.actual ? `and ${materialsObjective.actual} achievement on resume and LinkedIn completion tracked through staff-verified records.` : "",
  ]
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  const expandedExecutiveSummary = [
    payload.executive_summary,
    internsServedMetric?.value ? `The current dataset captures ${internsServedMetric.value} interns served across the connected reporting period.` : "",
    cleanTechObjective ? `Clean-tech awareness is being tracked against a goal of ${cleanTechObjective.target} with ${cleanTechObjective.actual} achieved.` : "",
    workplaceObjective ? `Workplace-readiness growth is being tracked against a goal of ${workplaceObjective.target} with ${workplaceObjective.actual} achieved.` : "",
  ]
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  const expandedGrantNarrative = [
    payload.narrative,
    ...(Array.isArray(payload.objectives) ? payload.objectives.slice(0, 3).map((item) => `${item.title} is currently measured against a goal of ${item.target} with ${item.actual} achieved.`) : []),
  ]
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
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
        <span>Goal: ${item.target}</span>
        <strong>Achieved: ${item.actual}</strong>
      </div>
    </div>
  `);
  const executiveSummary = document.getElementById("grant-executive-summary");
  const projectSummary = document.getElementById("grant-project-summary");
  const reportingPeriod = document.getElementById("grant-reporting-period");
  const quotesContainer = document.getElementById("grant-quotes");
  const narrative = document.getElementById("grant-narrative");
  if (executiveSummary) executiveSummary.textContent = expandedExecutiveSummary;
  if (projectSummary) projectSummary.textContent = projectSummaryText;
  if (reportingPeriod) reportingPeriod.textContent = payload.project?.reporting_period || `${payload.project?.cohort_year || "Current"} cohort`;
  if (quotesContainer) {
    const sourceQuotes = Array.isArray(payload.quotes) && payload.quotes.length ? payload.quotes : [payload.quote].filter(Boolean);
    const trimmedQuotes = sourceQuotes.slice(0, 3).map((quoteText) => {
      const normalized = String(quoteText || "").replace(/\s+/g, " ").trim();
      if (normalized.length <= 220) return normalized;
      const sentenceBreak = normalized.slice(0, 220).lastIndexOf('. ');
      const cutoff = sentenceBreak > 100 ? sentenceBreak + 1 : 217;
      return `${normalized.slice(0, cutoff).trim()}...`;
    });
    quotesContainer.innerHTML = trimmedQuotes.map((quoteText) => `
      <div class="grant-quote-card">
        <blockquote>"${escapeHtml(quoteText)}"</blockquote>
      </div>
    `).join("");
  }
  if (narrative) narrative.textContent = expandedGrantNarrative;
  wireGrantExport();
}

function wireGrantExport() {
  const exportButton = document.getElementById("export-pdf-button");
  if (exportButton && !exportButton.dataset.bound) {
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

  const copyButton = document.getElementById("copy-narrative-button");
  if (!copyButton || copyButton.dataset.bound) return;
  copyButton.dataset.bound = "true";
  copyButton.addEventListener("click", async (event) => {
    event.preventDefault();

    const grant = appState.grant || {};
    const executive = (grant.executive_summary || "").trim();
    const narrative = (grant.narrative || "").trim();

    if (!executive && !narrative) {
      setMessage("grant-copy-message", "No narrative is available to copy yet.", true);
      return;
    }

    const text = [
      executive ? `Executive Summary\n${executive}` : "",
      narrative ? `Grant-Ready Narrative\n${narrative}` : ""
    ].filter(Boolean).join("\n\n");

    try {
      await navigator.clipboard.writeText(text);
      setMessage("grant-copy-message", "Narrative copied.");
    } catch (error) {
      setMessage(
        "grant-copy-message",
        "Unable to copy narrative. Check clipboard permissions and try again.",
        true
      );
    }
  });
}

function wireLoginPage() {
  // Render the staff auth page with a stable sign-in/sign-up toggle.
  const signInPane = document.getElementById("signin-pane");
  const signUpPane = document.getElementById("signup-pane");
  const signInForm = document.getElementById("signin-form");
  const signUpForm = document.getElementById("signup-form");
  const signInEmail = document.getElementById("signin-email");
  const signInPassword = document.getElementById("signin-password");
  const signUpEmail = document.getElementById("signup-email");
  const signUpPassword = document.getElementById("signup-password");
  const signUpConfirmPassword = document.getElementById("signup-confirm-password");
  const title = document.getElementById("auth-title");
  const subtitle = document.getElementById("auth-subtitle");
  const modeButtons = Array.from(document.querySelectorAll("[data-auth-mode]"));
  const params = new URLSearchParams(window.location.search);

  function syncUrl(mode) {
    const nextParams = new URLSearchParams();
    if (mode === "signup") nextParams.set("mode", "signup");
    const nextQuery = nextParams.toString();
    const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
  }

  function setMode(mode) {
    const isSignup = mode === "signup";
    if (signInPane) signInPane.hidden = isSignup;
    if (signUpPane) signUpPane.hidden = !isSignup;
    if (title) title.textContent = isSignup ? "Sign up" : "Sign in";
    if (subtitle) {
      subtitle.textContent = isSignup
        ? "Create an approved staff account to enter the portal."
        : "Access your approved staff account.";
    }
    modeButtons.forEach((button) => {
      const active = button.dataset.authMode === mode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    setMessage("auth-message", "");
    syncUrl(mode);
    if (isSignup) {
      signUpEmail?.focus();
    } else {
      signInEmail?.focus();
    }
  }

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextMode = button.dataset.authMode === "signup" ? "signup" : "signin";
      setMode(nextMode);
    });
  });

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
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

  const initialMode = params.get("mode") === "signup" ? "signup" : "signin";
  setMode(initialMode);

  signInForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = (signInEmail?.value || "").trim().toLowerCase();
    const password = signInPassword?.value || "";

    if (!email || !password) {
      setMessage("auth-message", "Enter your email and password to continue.", true);
      return;
    }

    try {
      setMessage("auth-message", "Signing you in...");
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      window.location.href = "admin.html";
    } catch (error) {
      setMessage("auth-message", error?.message || "Unable to sign in.", true);
    }
  });

  signUpForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = (signUpEmail?.value || "").trim().toLowerCase();
    const password = signUpPassword?.value || "";
    const confirmPassword = signUpConfirmPassword?.value || "";

    if (!email || !password || !confirmPassword) {
      setMessage("auth-message", "Complete every field to create your portal access.", true);
      return;
    }

    if (password !== confirmPassword) {
      setMessage("auth-message", "Passwords do not match.", true);
      return;
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
    } catch (error) {
      setMessage("auth-message", error?.message || "Unable to create account.", true);
    }
  });
}

function renderGroupedHorizontalChart(targetId, items, options) {
  // Draw the paired Week 1 vs Week 8 horizontal comparison bars in SVG.
  const el = document.getElementById(targetId);
  if (!el) return;
  if (!items.length) {
    renderChartEmptyState(
      targetId,
      "Awaiting Week 8 post-survey data",
      "This score comparison will appear once the Week 8 post-survey is uploaded and matched to the Week 1 participant responses."
    );
    return;
  }
  const width = 880;
  const rowHeight = 66;
  const height = Math.max(items.length, 1) * rowHeight + 40;
  const labelSpace = 470;
  const barWidth = width - labelSpace - 48;

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
  // Draw the response-distribution comparison chart for the analytics page.
  const el = document.getElementById(targetId);
  if (!el) return;
  if (!items.length) {
    renderChartEmptyState(
      targetId,
      "Awaiting matched confidence responses",
      "The confidence distribution comparison will populate after Week 8 confidence responses are available for participants already found in Week 1."
    );
    return;
  }
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
  // Lightweight page router for the static multi-page frontend.
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
