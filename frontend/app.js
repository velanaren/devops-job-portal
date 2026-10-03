/* ============================================================
   InfraJobs — app.js
   Vanilla JS, ES6+. No frameworks, no build step.
   All filtering is client-side — no server round-trips.
   ============================================================ */

const API_BASE_URL = window.ENV_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : '');

// Number of job cards rendered per batch (infinite scroll).
const RENDER_BATCH_SIZE = 60;

// Number of skeleton placeholder cards shown while loading.
const SKELETON_COUNT = 9;

// Debounce delay for the search input, in milliseconds.
const SEARCH_DEBOUNCE_MS = 200;

// localStorage keys (per-viewer conveniences only — never required).
const STORAGE_SAVED = "infrajobs.saved";
const STORAGE_LAST_VISIT = "infrajobs.lastVisit";

// Default value of the "Posted Within" filter (days).
const DEFAULT_DAYS = "14";

// Role options for the multi-select. One option may cover several role_types.
const ROLE_OPTIONS = [
  { value: "devops",   label: "DevOps / DevSecOps",       types: ["devops"] },
  { value: "sre",      label: "SRE / Site Reliability",   types: ["sre"] },
  { value: "platform", label: "Platform Engineer",        types: ["platform"] },
  { value: "mlops",    label: "MLOps",                    types: ["mlops"] },
  { value: "cloud",    label: "Cloud Engineer",           types: ["cloud"] },
  { value: "infra",    label: "Infrastructure / Systems", types: ["infra"] },
  { value: "appsupport",  label: "Application / Production Support", types: ["appsupport"] },
  { value: "techsupport", label: "Technical / Product Support",      types: ["techsupport"] },
  { value: "itops",    label: "IT Operations / DBA",      types: ["itops"] },
];

// Roles selected by the "Support jobs" shortcut.
const SUPPORT_ROLES = ["appsupport", "techsupport"];

// Short role label shown on each card, keyed by role_type.
const ROLE_LABELS = {
  devops: "DevOps", sre: "SRE", platform: "Platform", mlops: "MLOps",
  cloud: "Cloud", infra: "Infra", appsupport: "App Support",
  techsupport: "Tech Support", itops: "IT Ops",
};

const LOCATION_OPTIONS = [
  "Remote Global", "Remote India", "Remote APAC", "Bengaluru", "Chennai", "Hyderabad",
  "Pune", "Mumbai", "Delhi NCR", "Other India",
].map(tag => ({ value: tag, label: tag }));

// Full deduplicated job list loaded once on page load — never mutated.
let allJobs = [];

// Currently filtered + sorted list, rendered incrementally in batches.
let visibleJobs = [];
let renderedCount = 0;

// Multi-select state.
const selectedRoles = new Set();
const selectedLocations = new Set();

// Saved job keys and the previous visit time (ISO date), from localStorage.
let savedKeys = new Set();
let lastVisitDate = null;

// --- DOM refs ------------------------------------------------
const jobsContainer  = document.getElementById("jobs-container");
const jobCount       = document.getElementById("job-count");
const lastUpdated    = document.getElementById("last-updated");
const loadingMsg     = document.getElementById("loading-msg");
const errorMsg       = document.getElementById("error-msg");
const btnClear       = document.getElementById("btn-clear");
const activeChips    = document.getElementById("active-chips");
const savedCount     = document.getElementById("saved-count");
const btnFilters     = document.getElementById("btn-filters-toggle");
const filtersCount   = document.getElementById("filters-toggle-count");
const filterRowMain  = document.getElementById("filter-row-main");

const filterSearch     = document.getElementById("filter-search");
const filterSort       = document.getElementById("filter-sort");
const filterRole       = document.getElementById("filter-role");
const filterLocation   = document.getElementById("filter-location");
const filterType       = document.getElementById("filter-type");
const filterSource     = document.getElementById("filter-source");
const filterExperience = document.getElementById("filter-experience");
const filterPosted     = document.getElementById("filter-posted");
const filterSaved      = document.getElementById("filter-saved");

const SELECT_FILTERS = [
  filterType, filterSource, filterExperience, filterPosted, filterSort,
];

// Single-value filter state ↔ URL query-string parameter mapping.
// Each entry: [element, param name, default value].
const URL_PARAM_MAP = [
  [filterSearch,     "q",      ""],
  [filterType,       "type",   ""],
  [filterSource,     "src",    ""],
  [filterExperience, "exp",    ""],
  [filterPosted,     "days",   DEFAULT_DAYS],
  [filterSort,       "sort",   "relevance"],
];

// Multi-select filters ↔ URL (comma-separated values).
const MULTI_PARAM_MAP = [
  [selectedRoles,     "role", ROLE_OPTIONS],
  [selectedLocations, "loc",  LOCATION_OPTIONS],
];

// --- Utilities -----------------------------------------------

/**
 * Escape a value for safe interpolation into HTML.
 * @param {*} value
 * @returns {string}
 */
const escapeHtml = (value) => {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
};

/**
 * Return the URL if it is http(s), otherwise an empty string.
 * Prevents javascript:/data: URLs from scraped data reaching href.
 * @param {string} url
 * @returns {string}
 */
const safeUrl = (url) => {
  if (typeof url !== "string") return "";
  return /^https?:\/\//i.test(url.trim()) ? url.trim() : "";
};

/**
 * Return a debounced wrapper around fn.
 * @param {Function} fn
 * @param {number} delayMs
 */
const debounce = (fn, delayMs) => {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
};

/**
 * Read a JSON value from localStorage, returning fallback on any error
 * (private mode, blocked storage, corrupt data).
 * @param {string} key
 * @param {*} fallback
 */
const storageGet = (key, fallback) => {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
};

/**
 * Write a JSON value to localStorage, ignoring errors.
 * @param {string} key
 * @param {*} value
 */
const storageSet = (key, value) => {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — feature degrades silently */
  }
};

/**
 * Stable identity for a job across days and sources.
 * @param {Object} job
 * @returns {string}
 */
const jobKey = (job) =>
  `${(job.company || "").trim().toLowerCase()}|${(job.title || "").trim().toLowerCase()}`;

/**
 * Describe how long ago a UTC timestamp was ("3h ago").
 * @param {Date} date
 * @returns {string}
 */
const timeAgo = (date) => {
  const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
  if (minutes < 1)  return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48)   return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
};

/**
 * Return a human-readable relative time string.
 * @param {string} dateStr - ISO date string (YYYY-MM-DD)
 */
const relativeTime = (dateStr) => {
  if (!dateStr) return "Unknown date";
  const posted = new Date(dateStr + "T00:00:00Z");
  const now = new Date();
  const diffMs = now - posted;
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7)  return `${days} days ago`;
  return `${Math.floor(days / 7)} week${days >= 14 ? "s" : ""} ago`;
};

/**
 * Map a location_tag to a badge CSS class and label.
 * @param {string} tag
 */
const locationBadge = (tag) => {
  switch (tag) {
    case "Remote Global": return { cls: "badge-remote-global", label: "🌍 Remote Global" };
    case "Remote India":  return { cls: "badge-remote-india",  label: "🇮🇳 Remote India" };
    case "Remote APAC":   return { cls: "badge-remote-global", label: "🌏 Remote APAC" };
    case "Bengaluru":     return { cls: "badge-city",          label: "📍 Bengaluru" };
    case "Chennai":       return { cls: "badge-city",          label: "📍 Chennai" };
    case "Hyderabad":     return { cls: "badge-city",          label: "📍 Hyderabad" };
    case "Pune":          return { cls: "badge-city",          label: "📍 Pune" };
    case "Mumbai":        return { cls: "badge-city",          label: "📍 Mumbai" };
    case "Delhi NCR":     return { cls: "badge-city",          label: "📍 Delhi NCR" };
    case "Other India":   return { cls: "badge-other-india",   label: "🇮🇳 Other India" };
    default:              return { cls: "badge-global",        label: tag || "Unknown" };
  }
};

/**
 * Return the numeric priority rank for a role_type.
 * Lower number = higher priority (shown first).
 * @param {string} role_type
 * @returns {number} 1–10
 */
const getRolePriority = (role_type) => {
  const ROLE_PRIORITY = {
    devops:      1,
    sre:         2,
    platform:    3,
    mlops:       4,
    cloud:       5,
    infra:       6,
    appsupport:  7,
    techsupport: 8,
    itops:       9,
  };
  return ROLE_PRIORITY[role_type] || 10;
};

/**
 * Compare two jobs by posted date, newest first.
 * @param {Object} a
 * @param {Object} b
 * @returns {number}
 */
const compareNewest = (a, b) => {
  const da = a.posted_date || a.fetched_date || "";
  const db = b.posted_date || b.fetched_date || "";
  return db.localeCompare(da);
};

/**
 * Sort a jobs array by the selected sort mode.
 * "relevance" — role priority (ascending) then newest first.
 * "newest"    — newest posted date first.
 * Returns a new array — does not mutate the input.
 * @param {Array} jobs
 * @param {string} mode
 * @returns {Array}
 */
const sortJobs = (jobs, mode) => [...jobs].sort((a, b) => {
  if (mode === "newest") return compareNewest(a, b);
  const roleDiff = getRolePriority(a.role_type) - getRolePriority(b.role_type);
  if (roleDiff !== 0) return roleDiff;
  return compareNewest(a, b);
});

/**
 * Collapse duplicate listings (same normalised company + title),
 * keeping the earliest-posted entry so "posted X ago" stays honest.
 * The kept entry gets an `alsoOn` list of the other sources' links.
 * Returns new objects — the API data is not mutated.
 * @param {Array} jobs
 * @returns {Array}
 */
const dedupJobs = (jobs) => {
  const groups = new Map();
  for (const job of jobs) {
    const key = jobKey(job);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(job);
  }
  const result = [];
  for (const group of groups.values()) {
    const dateOf = (j) => j.posted_date || j.fetched_date || "9999";
    const kept = group.reduce((best, j) => (dateOf(j) < dateOf(best) ? j : best));
    const alsoOn = group
      .filter(j => j !== kept && j.source_name !== kept.source_name)
      .map(j => ({ name: j.source_name, url: safeUrl(j.apply_url) }));
    result.push({ ...kept, alsoOn });
  }
  return result;
};

/**
 * Return the correct rel attribute value for a source attribution link.
 * RemoteOK ToS requires "follow" — no nofollow in the rel string.
 * @param {string} source_name
 * @returns {string}
 */
const getSourceLinkRel = (source_name) => {
  // Both branches return the same value today.
  // Keeping this helper makes per-source customisation straightforward.
  if (source_name === "RemoteOK") return "noopener noreferrer";
  return "noopener noreferrer";
};

/**
 * Build a comma-separated skills list into individual tag pills.
 * @param {string|null} skills
 */
const renderSkills = (skills) => {
  if (!skills) return "";
  return skills
    .split(",")
    .map(s => s.trim())
    .filter(Boolean)
    .slice(0, 6)
    .map(s => `<span class="tag">${escapeHtml(s)}</span>`)
    .join("");
};

/**
 * Humanise job_type for display.
 * @param {string} type
 */
const jobTypeLabel = (type) => {
  const map = { remote: "Remote", hybrid: "Hybrid", onsite: "On-site" };
  return map[type] || type || "";
};

/**
 * Humanise experience_level for display.
 * @param {string} level
 */
const expLabel = (level) => {
  const map = { entry: "Entry", mid: "Mid", senior: "Senior", staff: "Staff/Lead" };
  return map[level] || level || "";
};

// --- URL state sync ------------------------------------------

/**
 * Restore filter state from the current URL query string.
 * Unknown or missing params fall back to each filter's default.
 */
const readFiltersFromUrl = () => {
  const params = new URLSearchParams(window.location.search);
  for (const [el, param, fallback] of URL_PARAM_MAP) {
    el.value = params.get(param) ?? fallback;
    // Guard against invalid select values from a hand-edited URL.
    if (el.tagName === "SELECT" && el.value !== (params.get(param) ?? fallback)) {
      el.value = fallback;
    }
  }
  for (const [set, param, options] of MULTI_PARAM_MAP) {
    set.clear();
    const valid = new Set(options.map(o => o.value));
    (params.get(param) || "")
      .split(",")
      // Links shared before the support split used role=support.
      .flatMap(v => (param === "role" && v === "support" ? SUPPORT_ROLES : [v]))
      .filter(v => valid.has(v))
      .forEach(v => set.add(v));
  }
  filterSaved.checked = params.get("saved") === "1";
};

/**
 * Write the current filter state into the URL query string
 * (replaceState — no history spam). Defaults are omitted.
 */
const writeFiltersToUrl = () => {
  const params = new URLSearchParams();
  for (const [el, param, fallback] of URL_PARAM_MAP) {
    if (el.value && el.value !== fallback) params.set(param, el.value);
  }
  for (const [set, param] of MULTI_PARAM_MAP) {
    if (set.size) params.set(param, [...set].join(","));
  }
  if (filterSaved.checked) params.set("saved", "1");
  const query = params.toString();
  const newUrl = query
    ? `${window.location.pathname}?${query}`
    : window.location.pathname;
  window.history.replaceState(null, "", newUrl);
};

// --- Source dropdown -----------------------------------------

/**
 * Populate the Source filter options from the loaded job data,
 * preserving any pre-selected value restored from the URL.
 */
const populateSourceOptions = () => {
  // The URL may name a source before its <option> exists — re-read it here.
  const selected = new URLSearchParams(window.location.search).get("src") || "";
  const sources = [...new Set(allJobs.map(j => j.source_name).filter(Boolean))].sort();
  for (const source of sources) {
    const option = document.createElement("option");
    option.value = source;
    option.textContent = source;
    filterSource.appendChild(option);
  }
  if (selected && sources.includes(selected)) filterSource.value = selected;
};

// --- Card renderer -------------------------------------------

/**
 * Build and return a DOM article element for a single job.
 * All job fields are escaped before HTML interpolation; URLs are
 * validated as http(s) so scraped data can never inject markup.
 * @param {Object} job
 */
const buildCard = (job) => {
  const badge     = locationBadge(job.location_tag);
  const skills    = renderSkills(job.skills);
  const linkRel   = getSourceLinkRel(job.source_name);
  const sourceUrl = safeUrl(job.source_url);
  const applyUrl  = safeUrl(job.apply_url);
  const key       = jobKey(job);
  const isSaved   = savedKeys.has(key);
  const postedOn  = job.posted_date || job.fetched_date || "";
  const isNew     = lastVisitDate && postedOn && postedOn >= lastVisitDate;
  const roleLabel = ROLE_LABELS[job.role_type];

  const alsoOn = (job.alsoOn || [])
    .map(s => s.url
      ? `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.name)}</a>`
      : escapeHtml(s.name))
    .join(", ");

  const article = document.createElement("article");
  article.className = "job-card";
  article.innerHTML = `
    <div class="card-top">
      <h2 class="card-title">
        ${isNew ? `<span class="badge-new">New</span>` : ""}
        ${escapeHtml(job.title)}
      </h2>
      <button type="button" class="btn-save" data-key="${escapeHtml(key)}"
              aria-pressed="${isSaved}"
              aria-label="${isSaved ? "Remove from saved" : "Save job"}: ${escapeHtml(job.title)}"
              title="${isSaved ? "Saved" : "Save"}">${isSaved ? "★" : "☆"}</button>
    </div>
    <p class="card-company">${escapeHtml(job.company) || "—"}</p>
    <div class="card-badges">
      <span class="card-location-badge ${badge.cls}">${escapeHtml(badge.label)}</span>
      ${roleLabel ? `<span class="card-role">${escapeHtml(roleLabel)}</span>` : ""}
    </div>
    <div class="card-meta">
      ${job.location_raw ? `<span class="card-meta-item">📍 ${escapeHtml(job.location_raw)}</span>` : ""}
      ${job.job_type     ? `<span class="card-meta-item">💼 ${escapeHtml(jobTypeLabel(job.job_type))}</span>` : ""}
      ${job.experience_level ? `<span class="card-meta-item">🎯 ${escapeHtml(expLabel(job.experience_level))}</span>` : ""}
      <span class="card-meta-item">🕐 ${escapeHtml(relativeTime(postedOn))}</span>
    </div>
    ${skills ? `<div class="card-tags">${skills}</div>` : ""}
    <div class="card-footer">
      <span class="card-source">
        ${sourceUrl
          ? `via <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="${linkRel}">${escapeHtml(job.source_name)}</a>`
          : `via ${escapeHtml(job.source_name)}`}
        ${alsoOn ? `<span class="card-also-on">· also on ${alsoOn}</span>` : ""}
      </span>
      ${applyUrl
        ? `<a class="btn-apply" href="${escapeHtml(applyUrl)}" target="_blank" rel="${linkRel}">Apply →</a>`
        : ""}
    </div>
  `;
  return article;
};

// --- Skeleton loading state ----------------------------------

/**
 * Render skeleton placeholder cards while the job data loads.
 */
const renderSkeletons = () => {
  const fragment = document.createDocumentFragment();
  for (let i = 0; i < SKELETON_COUNT; i++) {
    const card = document.createElement("div");
    card.className = "job-card skeleton-card";
    card.innerHTML = `
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line short"></div>
      <div class="skeleton skeleton-footer"></div>
    `;
    fragment.appendChild(card);
  }
  jobsContainer.appendChild(fragment);
};

// --- Incremental rendering (infinite scroll) -----------------

// Sentinel element observed to trigger the next render batch.
const sentinel = document.createElement("div");
sentinel.className = "scroll-sentinel";

const observer = new IntersectionObserver((entries) => {
  if (entries.some(e => e.isIntersecting)) renderNextBatch();
}, { rootMargin: "600px" });

// Scroll-listener fallback: covers environments where the
// IntersectionObserver stays dormant (e.g. some embedded webviews).
let scrollCheckPending = false;
window.addEventListener("scroll", () => {
  if (scrollCheckPending || !sentinel.isConnected) return;
  scrollCheckPending = true;
  requestAnimationFrame(() => {
    scrollCheckPending = false;
    if (!sentinel.isConnected) return;
    if (sentinel.getBoundingClientRect().top < window.innerHeight + 600) {
      renderNextBatch();
    }
  });
}, { passive: true });

/**
 * Append the next batch of visibleJobs cards to the container.
 * Disconnects the sentinel once everything is rendered.
 */
const renderNextBatch = () => {
  const batch = visibleJobs.slice(renderedCount, renderedCount + RENDER_BATCH_SIZE);
  if (batch.length === 0) {
    observer.unobserve(sentinel);
    sentinel.remove();
    return;
  }

  const fragment = document.createDocumentFragment();
  batch.forEach(job => fragment.appendChild(buildCard(job)));
  jobsContainer.insertBefore(fragment, sentinel.parentNode === jobsContainer ? sentinel : null);
  renderedCount += batch.length;

  if (renderedCount >= visibleJobs.length) {
    observer.unobserve(sentinel);
    sentinel.remove();
  }
};

/**
 * Render a list of jobs into the container, replacing current content.
 * Renders the first batch immediately; further batches load on scroll.
 * @param {Array} jobs
 */
const renderJobs = (jobs) => {
  visibleJobs = jobs;
  renderedCount = 0;
  observer.unobserve(sentinel);
  jobsContainer.innerHTML = "";

  if (jobs.length === 0) {
    jobsContainer.appendChild(buildEmptyState());
  } else {
    if (jobs.length > RENDER_BATCH_SIZE) {
      jobsContainer.appendChild(sentinel);
      observer.observe(sentinel);
    }
    renderNextBatch();
  }

  jobCount.textContent = `${jobs.length} job${jobs.length !== 1 ? "s" : ""} found`;
};

// --- Empty state -------------------------------------------

/**
 * Build a helpful "no results" block with next-step suggestions.
 * @returns {HTMLElement}
 */
const buildEmptyState = () => {
  const box = document.createElement("div");
  box.className = "no-results";
  const tips = [];
  if (filterSaved.checked && savedKeys.size === 0) {
    tips.push("You have no saved jobs yet — tap ☆ on a job to save it.");
  } else {
    if (filterSearch.value.trim()) tips.push("Try fewer or different search words.");
    if (selectedLocations.size)    tips.push("Add more locations, or include Remote Global.");
    if (filterPosted.value !== DEFAULT_DAYS) tips.push("Widen “Posted Within” to 14 days.");
    if (filterExperience.value)    tips.push("Remove the Experience filter.");
  }
  box.innerHTML = `
    <p class="no-results-title">No jobs match your current filters.</p>
    ${tips.length ? `<ul class="no-results-tips">${tips.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>` : ""}
    <button type="button" class="btn-clear btn-clear-inline">Clear all filters</button>
  `;
  box.querySelector("button").addEventListener("click", clearFilters);
  return box;
};

// --- Filtering -----------------------------------------------

/**
 * Snapshot the current filter selections.
 * @returns {Object}
 */
const readFilterState = () => {
  const days = parseInt(filterPosted.value, 10);
  const cutoff = new Date();
  cutoff.setUTCDate(cutoff.getUTCDate() - days);
  cutoff.setUTCHours(0, 0, 0, 0);
  const roleTypes = new Set(
    ROLE_OPTIONS.filter(o => selectedRoles.has(o.value)).flatMap(o => o.types)
  );
  return {
    words:      filterSearch.value.trim().toLowerCase().split(/\s+/).filter(Boolean),
    roleTypes,
    locations:  selectedLocations,
    type:       filterType.value,
    source:     filterSource.value,
    experience: filterExperience.value,
    savedOnly:  filterSaved.checked,
    cutoff,
  };
};

/**
 * Return true if the job passes every filter in state, optionally
 * ignoring one facet (used to compute option counts for that facet).
 * @param {Object} job
 * @param {Object} state - from readFilterState()
 * @param {string} [ignore] - "role" or "location"
 */
const jobMatches = (job, state, ignore) => {
  if (state.words.length) {
    const haystack = [
      job.title, job.company, job.skills, job.location_raw, job.location_tag,
      ROLE_LABELS[job.role_type], job.source_name,
    ].join(" ").toLowerCase();
    if (!state.words.every(w => haystack.includes(w))) return false;
  }
  if (ignore !== "role" && state.roleTypes.size && !state.roleTypes.has(job.role_type)) return false;
  if (ignore !== "location" && state.locations.size && !state.locations.has(job.location_tag)) return false;
  if (state.type       && job.job_type         !== state.type)       return false;
  if (state.source     && job.source_name      !== state.source)     return false;
  if (state.experience && job.experience_level !== state.experience) return false;
  if (state.savedOnly  && !savedKeys.has(jobKey(job)))               return false;

  const dateStr = job.posted_date || job.fetched_date;
  if (dateStr && new Date(dateStr + "T00:00:00Z") < state.cutoff) return false;
  return true;
};

/**
 * Build (or rebuild) a multi-select checkbox list with live counts.
 * Counts reflect all other active filters, so a user sees how many
 * jobs each option would add.
 * @param {HTMLElement} root - .multi-select wrapper
 * @param {Array} options - [{value, label, types?}]
 * @param {Set} selected
 * @param {Function} countFor - option → number
 * @param {string} allLabel - summary text when nothing is selected
 */
const renderMultiSelect = (root, options, selected, countFor, allLabel) => {
  const list = root.querySelector(".multi-options");
  list.innerHTML = options.map(o => `
    <label class="multi-option">
      <input type="checkbox" value="${escapeHtml(o.value)}" ${selected.has(o.value) ? "checked" : ""} />
      <span>${escapeHtml(o.label)}</span>
      <span class="multi-count">${countFor(o)}</span>
    </label>`).join("");

  const summary = root.querySelector(".multi-summary span");
  if (selected.size === 0) summary.textContent = allLabel;
  else if (selected.size === 1) {
    summary.textContent = options.find(o => selected.has(o.value))?.label || allLabel;
  } else summary.textContent = `${selected.size} selected`;
};

/**
 * Recompute counts and redraw both multi-selects.
 * @param {Object} state
 */
const refreshMultiSelects = (state) => {
  const forRole = allJobs.filter(j => jobMatches(j, state, "role"));
  const forLoc  = allJobs.filter(j => jobMatches(j, state, "location"));
  renderMultiSelect(filterRole, ROLE_OPTIONS, selectedRoles,
    o => forRole.filter(j => o.types.includes(j.role_type)).length, "All Roles");
  renderMultiSelect(filterLocation, LOCATION_OPTIONS, selectedLocations,
    o => forLoc.filter(j => j.location_tag === o.value).length, "All Locations");
};

/**
 * Render removable chips for every active (non-default) filter.
 * @returns {number} number of active filters
 */
const renderChips = () => {
  const chips = [];
  const q = filterSearch.value.trim();
  if (q) chips.push({ label: `“${q}”`, clear: () => { filterSearch.value = ""; } });
  for (const v of selectedRoles) {
    const label = ROLE_OPTIONS.find(o => o.value === v)?.label || v;
    chips.push({ label, clear: () => selectedRoles.delete(v) });
  }
  for (const v of selectedLocations) chips.push({ label: v, clear: () => selectedLocations.delete(v) });
  const selectChip = (el, fallback) => {
    if (el.value !== fallback) {
      chips.push({ label: el.options[el.selectedIndex].text, clear: () => { el.value = fallback; } });
    }
  };
  selectChip(filterType, "");
  selectChip(filterSource, "");
  selectChip(filterExperience, "");
  selectChip(filterPosted, DEFAULT_DAYS);
  if (filterSaved.checked) chips.push({ label: "★ Saved only", clear: () => { filterSaved.checked = false; } });

  activeChips.innerHTML = "";
  chips.forEach(chip => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.setAttribute("aria-label", `Remove filter ${chip.label}`);
    btn.innerHTML = `${escapeHtml(chip.label)} <span aria-hidden="true">×</span>`;
    btn.addEventListener("click", () => { chip.clear(); applyFilters(); });
    activeChips.appendChild(btn);
  });
  activeChips.hidden = chips.length === 0;
  return chips.length;
};

/**
 * Apply all active filter selections to allJobs and re-render.
 * Runs entirely in memory — no network requests.
 */
const applyFilters = () => {
  const state = readFilterState();
  const filtered = allJobs.filter(job => jobMatches(job, state));

  renderJobs(sortJobs(filtered, filterSort.value));
  refreshMultiSelects(state);
  writeFiltersToUrl();

  const activeCount = renderChips();
  filtersCount.textContent = activeCount ? `(${activeCount})` : "";
  savedCount.textContent = savedKeys.size ? `(${savedKeys.size})` : "";
  btnClear.hidden = activeCount === 0 && filterSort.value === "relevance";
};

// --- Clear filters -------------------------------------------

const clearFilters = () => {
  for (const [el, , fallback] of URL_PARAM_MAP) el.value = fallback;
  selectedRoles.clear();
  selectedLocations.clear();
  filterSaved.checked = false;
  applyFilters();
};

// --- Saved jobs ----------------------------------------------

/**
 * Toggle a job's saved state and persist it to localStorage.
 * Updates the clicked button in place (no full re-render) unless the
 * "Saved only" view is active, where the list must shrink.
 * @param {HTMLButtonElement} btn
 */
const toggleSaved = (btn) => {
  const key = btn.dataset.key;
  if (savedKeys.has(key)) savedKeys.delete(key);
  else savedKeys.add(key);
  storageSet(STORAGE_SAVED, [...savedKeys]);

  if (filterSaved.checked) {
    applyFilters();
    return;
  }
  const saved = savedKeys.has(key);
  btn.textContent = saved ? "★" : "☆";
  btn.setAttribute("aria-pressed", String(saved));
  btn.title = saved ? "Saved" : "Save";
  savedCount.textContent = savedKeys.size ? `(${savedKeys.size})` : "";
};

// --- Data fetch ----------------------------------------------

/**
 * Show when the data was last refreshed, e.g. "Updated 3h ago",
 * with the full local time on hover.
 * @param {string|null} fetchedAt - UTC "YYYY-MM-DDTHH:MM:SS"
 */
const renderLastUpdated = (fetchedAt) => {
  const date = fetchedAt ? new Date(`${fetchedAt.replace(" ", "T")}Z`) : null;
  if (!date || Number.isNaN(date.getTime())) {
    lastUpdated.textContent = "Last updated: unknown";
    return;
  }
  lastUpdated.textContent = `Updated ${timeAgo(date)} · refreshed daily`;
  lastUpdated.title = date.toLocaleString();
};

/**
 * Fetch all jobs from the API once on page load.
 * Dedupes and stores the result in allJobs, then applies any
 * filters restored from the URL and renders.
 */
const loadJobs = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/jobs`);
    if (!response.ok) throw new Error(`API returned ${response.status}`);

    const data = await response.json();
    allJobs = dedupJobs(data.jobs || []);

    jobsContainer.innerHTML = "";

    renderLastUpdated(data.fetched_at);

    populateSourceOptions();
    applyFilters();
  } catch (err) {
    jobsContainer.innerHTML = "";
    errorMsg.textContent = `Failed to load jobs: ${err.message}`;
    errorMsg.hidden = false;
    jobCount.textContent = "0 jobs found";
    console.error("Job fetch error:", err);
  }
};

// --- Initialise ----------------------------------------------

savedKeys = new Set(storageGet(STORAGE_SAVED, []));
lastVisitDate = storageGet(STORAGE_LAST_VISIT, null);
storageSet(STORAGE_LAST_VISIT, new Date().toISOString().slice(0, 10));

if (loadingMsg) loadingMsg.remove();
renderSkeletons();
readFiltersFromUrl();

SELECT_FILTERS.forEach(el => el.addEventListener("change", applyFilters));
filterSaved.addEventListener("change", applyFilters);
filterSearch.addEventListener("input", debounce(applyFilters, SEARCH_DEBOUNCE_MS));
btnClear.addEventListener("click", clearFilters);

// Multi-select checkboxes (event delegation — lists are rebuilt on each filter).
[[filterRole, selectedRoles], [filterLocation, selectedLocations]].forEach(([root, set]) => {
  root.addEventListener("change", (e) => {
    if (e.target.type !== "checkbox") return;
    if (e.target.checked) set.add(e.target.value);
    else set.delete(e.target.value);
    applyFilters();
  });
});

// --- Multi-select open/close (button + panel; no <details>) ---

/**
 * Open or close one multi-select panel, closing any other open one.
 * @param {HTMLElement} root - .multi-select wrapper
 * @param {boolean} open
 */
const setMultiOpen = (root, open) => {
  if (open) document.querySelectorAll(".multi-select.is-open").forEach(r => r !== root && setMultiOpen(r, false));
  root.classList.toggle("is-open", open);
  root.querySelector(".multi-options").hidden = !open;
  root.querySelector(".multi-summary").setAttribute("aria-expanded", String(open));
};

[filterRole, filterLocation].forEach(root => {
  root.querySelector(".multi-summary").addEventListener("click", () => {
    setMultiOpen(root, !root.classList.contains("is-open"));
  });
});

// Close an open multi-select when clicking anywhere outside it.
document.addEventListener("click", (e) => {
  // Option lists are rebuilt on every change, so the clicked node may already
  // be detached — that click was inside a panel, not outside.
  if (!e.target.isConnected) return;
  document.querySelectorAll(".multi-select.is-open").forEach(root => {
    if (!root.contains(e.target)) setMultiOpen(root, false);
  });
});

// "Support jobs" shortcut: select exactly the two support roles.
document.getElementById("btn-support-view").addEventListener("click", () => {
  selectedRoles.clear();
  SUPPORT_ROLES.forEach(r => selectedRoles.add(r));
  applyFilters();
});

// Save buttons (delegated).
jobsContainer.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-save");
  if (btn) toggleSaved(btn);
});

// Mobile: collapse the filter grid behind a toggle button.
btnFilters.addEventListener("click", () => {
  const open = btnFilters.getAttribute("aria-expanded") !== "true";
  btnFilters.setAttribute("aria-expanded", String(open));
  filterRowMain.classList.toggle("is-open", open);
});

// Keyboard: "/" focuses search; Escape clears it or closes a multi-select.
document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName);
  if (e.key === "/" && !typing) {
    e.preventDefault();
    filterSearch.focus();
  } else if (e.key === "Escape") {
    const openMenu = document.querySelector(".multi-select.is-open");
    if (openMenu) {
      setMultiOpen(openMenu, false);
      openMenu.querySelector(".multi-summary").focus();
    } else if (document.activeElement === filterSearch && filterSearch.value) {
      filterSearch.value = "";
      applyFilters();
    }
  }
});

loadJobs();
