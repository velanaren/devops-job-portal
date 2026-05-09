/* ============================================================
   DevOps Job Portal — app.js
   Vanilla JS, ES6+. No frameworks, no build step.
   All filtering is client-side — no server round-trips.
   ============================================================ */

const API_BASE_URL = "http://localhost:8000";

// Full job list loaded once on page load — never mutated.
let allJobs = [];

// --- DOM refs ------------------------------------------------
const jobsContainer  = document.getElementById("jobs-container");
const jobCount       = document.getElementById("job-count");
const lastUpdated    = document.getElementById("last-updated");
const loadingMsg     = document.getElementById("loading-msg");
const errorMsg       = document.getElementById("error-msg");
const btnClear       = document.getElementById("btn-clear");

const filterRole       = document.getElementById("filter-role");
const filterLocation   = document.getElementById("filter-location");
const filterType       = document.getElementById("filter-type");
const filterSource     = document.getElementById("filter-source");
const filterExperience = document.getElementById("filter-experience");
const filterPosted     = document.getElementById("filter-posted");

const ALL_FILTERS = [
  filterRole, filterLocation, filterType,
  filterSource, filterExperience, filterPosted,
];

// --- Utilities -----------------------------------------------

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
    case "Chennai":       return { cls: "badge-city",          label: "📍 Chennai" };
    case "Bengaluru":     return { cls: "badge-city",          label: "📍 Bengaluru" };
    default:              return { cls: "badge-city",          label: "📍 Other" };
  }
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
    .map(s => `<span class="tag">${s}</span>`)
    .join("");
};

/**
 * Humanise a source_name for display.
 * @param {string} name
 */
const sourceLabel = (name) => {
  const map = {
    HN: "Hacker News",
    RemoteOK: "RemoteOK",
    Remotive: "Remotive",
    Jobicy: "Jobicy",
    Arbeitnow: "Arbeitnow",
    Greenhouse: "Greenhouse",
    Lever: "Lever",
    Ashby: "Ashby",
  };
  return map[name] || name;
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

// --- Card renderer -------------------------------------------

/**
 * Build and return a DOM article element for a single job.
 * @param {Object} job
 */
const buildCard = (job) => {
  const badge = locationBadge(job.location_tag);
  const skills = renderSkills(job.skills);

  const article = document.createElement("article");
  article.className = "job-card";
  article.innerHTML = `
    <div class="card-top">
      <h2 class="card-title">${job.title}</h2>
      <span class="card-location-badge ${badge.cls}">${badge.label}</span>
    </div>
    <p class="card-company">${job.company || "—"}</p>
    <div class="card-meta">
      ${job.location_raw ? `<span class="card-meta-item">📍 ${job.location_raw}</span>` : ""}
      ${job.job_type     ? `<span class="card-meta-item">💼 ${jobTypeLabel(job.job_type)}</span>` : ""}
      ${job.experience_level ? `<span class="card-meta-item">🎯 ${expLabel(job.experience_level)}</span>` : ""}
      <span class="card-meta-item">🕐 ${relativeTime(job.posted_date || job.fetched_date)}</span>
    </div>
    ${skills ? `<div class="card-tags">${skills}</div>` : ""}
    <div class="card-footer">
      <span class="card-source">
        via <a href="${job.source_url}" target="_blank" rel="noopener noreferrer">${sourceLabel(job.source_name)}</a>
      </span>
      <a class="btn-apply"
         href="${job.apply_url}"
         target="_blank"
         rel="noopener noreferrer">
        Apply →
      </a>
    </div>
  `;
  return article;
};

// --- Render --------------------------------------------------

/**
 * Render a list of jobs into the container, replacing current content.
 * @param {Array} jobs
 */
const renderJobs = (jobs) => {
  jobsContainer.innerHTML = "";

  if (jobs.length === 0) {
    const p = document.createElement("p");
    p.className = "no-results";
    p.textContent = "No jobs match your current filters.";
    jobsContainer.appendChild(p);
  } else {
    const fragment = document.createDocumentFragment();
    jobs.forEach(job => fragment.appendChild(buildCard(job)));
    jobsContainer.appendChild(fragment);
  }

  jobCount.textContent = `${jobs.length} job${jobs.length !== 1 ? "s" : ""} found`;
};

// --- Filtering -----------------------------------------------

/**
 * Apply all active filter selections to allJobs and re-render.
 * Runs entirely in memory — no network requests.
 */
const applyFilters = () => {
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
    if (role       && job.role_type        !== role)      return false;
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

  renderJobs(filtered);

  // Show "Clear all filters" only when a non-default filter is active.
  const hasActiveFilter =
    role || location || type || source || experience || (postedDays !== 7);
  btnClear.hidden = !hasActiveFilter;
};

// --- Clear filters -------------------------------------------

const clearFilters = () => {
  filterRole.value       = "";
  filterLocation.value   = "";
  filterType.value       = "";
  filterSource.value     = "";
  filterExperience.value = "";
  filterPosted.value     = "7";
  btnClear.hidden        = true;
  renderJobs(allJobs);
  jobCount.textContent   = `${allJobs.length} job${allJobs.length !== 1 ? "s" : ""} found`;
};

// --- Data fetch ----------------------------------------------

/**
 * Fetch all jobs from the API once on page load.
 * Stores result in allJobs, then renders.
 */
const loadJobs = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/jobs`);
    if (!response.ok) throw new Error(`API returned ${response.status}`);

    const data = await response.json();
    allJobs = data.jobs || [];

    loadingMsg.remove();

    lastUpdated.textContent = data.fetched_at
      ? `Last updated: ${data.fetched_at} UTC`
      : "Last updated: unknown";

    renderJobs(allJobs);
  } catch (err) {
    loadingMsg.remove();
    errorMsg.textContent = `Failed to load jobs: ${err.message}`;
    errorMsg.hidden = false;
    jobCount.textContent = "0 jobs found";
    console.error("Job fetch error:", err);
  }
};

// --- Initialise ----------------------------------------------

ALL_FILTERS.forEach(el => el.addEventListener("change", applyFilters));
btnClear.addEventListener("click", clearFilters);

loadJobs();
