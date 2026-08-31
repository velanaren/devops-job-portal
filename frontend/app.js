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

// Full deduplicated job list loaded once on page load — never mutated.
let allJobs = [];

// Currently filtered + sorted list, rendered incrementally in batches.
let visibleJobs = [];
let renderedCount = 0;

// --- DOM refs ------------------------------------------------
const jobsContainer  = document.getElementById("jobs-container");
const jobCount       = document.getElementById("job-count");
const lastUpdated    = document.getElementById("last-updated");
const loadingMsg     = document.getElementById("loading-msg");
const errorMsg       = document.getElementById("error-msg");
const btnClear       = document.getElementById("btn-clear");

const filterSearch     = document.getElementById("filter-search");
const filterSort       = document.getElementById("filter-sort");
const filterRole       = document.getElementById("filter-role");
const filterLocation   = document.getElementById("filter-location");
const filterType       = document.getElementById("filter-type");
const filterSource     = document.getElementById("filter-source");
const filterExperience = document.getElementById("filter-experience");
const filterPosted     = document.getElementById("filter-posted");

const SELECT_FILTERS = [
  filterRole, filterLocation, filterType,
  filterSource, filterExperience, filterPosted, filterSort,
];

// Filter state ↔ URL query-string parameter mapping.
// Each entry: [element, param name, default value].
const URL_PARAM_MAP = [
  [filterSearch,     "q",      ""],
  [filterRole,       "role",   ""],
  [filterLocation,   "loc",    ""],
  [filterType,       "type",   ""],
  [filterSource,     "src",    ""],
  [filterExperience, "exp",    ""],
  [filterPosted,     "days",   "14"],
  [filterSort,       "sort",   "relevance"],
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
 * @param {Array} jobs
 * @returns {Array}
 */
const dedupJobs = (jobs) => {
  const seen = new Map();
  for (const job of jobs) {
    const key = `${(job.company || "").trim().toLowerCase()}|${(job.title || "").trim().toLowerCase()}`;
    const existing = seen.get(key);
    if (!existing) {
      seen.set(key, job);
    } else {
      // Keep whichever was posted earliest (oldest date wins).
      const existingDate = existing.posted_date || existing.fetched_date || "";
      const jobDate = job.posted_date || job.fetched_date || "";
      if (jobDate && (!existingDate || jobDate < existingDate)) {
        seen.set(key, job);
      }
    }
  }
  return [...seen.values()];
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

  const article = document.createElement("article");
  article.className = "job-card";
  article.innerHTML = `
    <div class="card-top">
      <h2 class="card-title">${escapeHtml(job.title)}</h2>
      <span class="card-location-badge ${badge.cls}">${escapeHtml(badge.label)}</span>
    </div>
    <p class="card-company">${escapeHtml(job.company) || "—"}</p>
    <div class="card-meta">
      ${job.location_raw ? `<span class="card-meta-item">📍 ${escapeHtml(job.location_raw)}</span>` : ""}
      ${job.job_type     ? `<span class="card-meta-item">💼 ${escapeHtml(jobTypeLabel(job.job_type))}</span>` : ""}
      ${job.experience_level ? `<span class="card-meta-item">🎯 ${escapeHtml(expLabel(job.experience_level))}</span>` : ""}
      <span class="card-meta-item">🕐 ${escapeHtml(relativeTime(job.posted_date || job.fetched_date))}</span>
    </div>
    ${skills ? `<div class="card-tags">${skills}</div>` : ""}
    <div class="card-footer">
      <span class="card-source">
        ${sourceUrl
          ? `via <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="${linkRel}">${escapeHtml(job.source_name)}</a>`
          : `via ${escapeHtml(job.source_name)}`}
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
    const p = document.createElement("p");
    p.className = "no-results";
    p.textContent = "No jobs match your current filters.";
    jobsContainer.appendChild(p);
  } else {
    if (jobs.length > RENDER_BATCH_SIZE) {
      jobsContainer.appendChild(sentinel);
      observer.observe(sentinel);
    }
    renderNextBatch();
  }

  jobCount.textContent = `${jobs.length} job${jobs.length !== 1 ? "s" : ""} found`;
};

// --- Filtering -----------------------------------------------

/**
 * Apply all active filter selections to allJobs and re-render.
 * Runs entirely in memory — no network requests.
 */
const applyFilters = () => {
  const search     = filterSearch.value.trim().toLowerCase();
  const role       = filterRole.value;
  const location   = filterLocation.value;
  const type       = filterType.value;
  const source     = filterSource.value;
  const experience = filterExperience.value;
  const postedDays = parseInt(filterPosted.value, 10);

  const cutoff = new Date();
  cutoff.setUTCDate(cutoff.getUTCDate() - postedDays);
  cutoff.setUTCHours(0, 0, 0, 0);

  const filtered = allJobs.filter(job => {
    if (search) {
      const haystack = `${job.title || ""} ${job.company || ""} ${job.skills || ""}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    if (role) {
      // "support" is a merged option that matches both appsupport and techsupport.
      if (role === "support") {
        if (job.role_type !== "appsupport" && job.role_type !== "techsupport") return false;
      } else {
        if (job.role_type !== role) return false;
      }
    }
    if (location   && job.location_tag     !== location)  return false;
    if (type       && job.job_type         !== type)      return false;
    if (source     && job.source_name      !== source)    return false;
    if (experience && job.experience_level !== experience) return false;

    // Posted within filter.
    const dateStr = job.posted_date || job.fetched_date;
    if (dateStr) {
      const posted = new Date(dateStr + "T00:00:00Z");
      if (posted < cutoff) return false;
    }

    return true;
  });

  renderJobs(sortJobs(filtered, filterSort.value));
  writeFiltersToUrl();

  // Show "Clear all filters" only when a non-default filter is active.
  const hasActiveFilter =
    search || role || location || type || source || experience ||
    (postedDays !== 14) || (filterSort.value !== "relevance");
  btnClear.hidden = !hasActiveFilter;
};

// --- Clear filters -------------------------------------------

const clearFilters = () => {
  for (const [el, , fallback] of URL_PARAM_MAP) el.value = fallback;
  applyFilters();
};

// --- Data fetch ----------------------------------------------

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

    lastUpdated.textContent = data.fetched_at
      ? `Last updated: ${data.fetched_at} UTC`
      : "Last updated: unknown";

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

if (loadingMsg) loadingMsg.remove();
renderSkeletons();
readFiltersFromUrl();

SELECT_FILTERS.forEach(el => el.addEventListener("change", applyFilters));
filterSearch.addEventListener("input", debounce(applyFilters, SEARCH_DEBOUNCE_MS));
btnClear.addEventListener("click", clearFilters);

loadJobs();
