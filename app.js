// Retract Radar - main application script

/** Global array holding all retracted works loaded from data/retractions.json. */
let retractions = [];

const DATA_URL = "data/retractions.json";

/**
 * Fetches the retractions dataset and stores it in the global `retractions`
 * array, then renders the initial (unfiltered) results.
 */
async function loadRetractions() {
  const grid = document.getElementById("results-grid");
  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    retractions = await response.json();
    renderResults(retractions);
  } catch (error) {
    console.error("Failed to load retractions data:", error);
    if (grid) {
      grid.innerHTML = `
        <p class="col-span-full text-center text-red-400">
          Failed to load retractions data. Please try again later.
        </p>
      `;
    }
  }
}

/**
 * Filters the global `retractions` array by matching the query against
 * each work's title or DOI (case-insensitive, substring match).
 * @param {string} query
 * @returns {Array<Object>}
 */
function filterRetractions(query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return retractions;
  }
  return retractions.filter((work) => {
    const title = (work.title || "").toLowerCase();
    const doi = (work.doi || "").toLowerCase();
    return title.includes(normalized) || doi.includes(normalized);
  });
}

/** Escapes HTML special characters to prevent injection when rendering text. */
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return map[char];
  });
}

/**
 * Renders an array of retraction records as HTML cards inside the
 * '#results-grid' container.
 * @param {Array<Object>} results
 */
function renderResults(results) {
  const grid = document.getElementById("results-grid");
  if (!grid) return;

  if (!results.length) {
    grid.innerHTML = `
      <p class="col-span-full text-center text-slate-400">
        No matching retractions found.
      </p>
    `;
    return;
  }

  grid.innerHTML = results
    .map((work) => {
      const title = escapeHtml(work.title || "Untitled");
      const doi = work.doi || "";
      const doiHtml = doi
        ? `<a href="${escapeHtml(doi)}" target="_blank" rel="noopener noreferrer" class="text-red-400 hover:underline break-all">${escapeHtml(doi)}</a>`
        : `<span class="text-slate-500">No DOI</span>`;
      const topic = escapeHtml(work.primary_topic || "Unknown topic");
      const publisher = escapeHtml(work.host_venue || "Unknown publisher");
      const year = escapeHtml(work.publication_year ?? "Unknown year");

      return `
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col gap-2">
          <h3 class="text-lg font-semibold text-slate-100">${title}</h3>
          <p class="text-sm text-slate-400">${doiHtml}</p>
          <div class="mt-2 flex flex-wrap gap-2 text-xs">
            <span class="px-2 py-1 rounded-full bg-slate-800 text-slate-300">${topic}</span>
            <span class="px-2 py-1 rounded-full bg-slate-800 text-slate-300">${publisher}</span>
            <span class="px-2 py-1 rounded-full bg-slate-800 text-slate-300">${year}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("Retract Radar app loaded.");

  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (event) => {
      const filtered = filterRetractions(event.target.value);
      renderResults(filtered);
    });
  }

  loadRetractions();
});
