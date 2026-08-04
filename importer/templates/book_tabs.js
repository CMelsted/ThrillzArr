function openTab(tabId) {
    const tabLinks = document.querySelectorAll(".tab");
    tabLinks.forEach(tab => {
        tab.classList.remove("is-active");
    });

    const tabPanes = document.querySelectorAll(".tab-pane");
    tabPanes.forEach(pane => {
        pane.style.display = "none";
    });

    document.getElementById(tabId).style.display = "block";
    document.getElementById(`${tabId}-tab`).classList.add("is-active");
}

async function postForm(form) {
    const body = new URLSearchParams();
    form.querySelectorAll('input[type="hidden"]').forEach(input => {
        body.append(input.name, input.value);
    });

    try {
        const response = await fetch(form.action, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body: body,
        });
        return await response.json();
    } catch (error) {
        return { ok: false, error: `Could not reach the server: ${error}` };
    }
}

function showEmptyStateIfNeeded(tabPane) {
    if (tabPane.querySelectorAll(".book-row").length > 0) return;

    const emptyState = tabPane.querySelector(".empty-state");
    if (emptyState) emptyState.style.display = "";

    const clearAll = document.querySelector(`[data-clear-all="${tabPane.dataset.clearStatus || ""}"]`);
    if (clearAll) clearAll.style.display = "none";
}

function removeBookRow(bookId) {
    const row = document.querySelector(`.book-row[data-book-id="${bookId}"]`);
    if (!row) return;
    const tabPane = row.closest(".tab-pane");
    row.remove();
    if (tabPane) showEmptyStateIfNeeded(tabPane);
}

async function handleAbandonSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector("button");
    button.classList.add("is-loading");
    const result = await postForm(form);
    button.classList.remove("is-loading");

    if (!result.ok) {
        window.alert(result.error || "Could not abandon this job.");
        return;
    }
    removeBookRow(result.book_id);
}

async function handleClearEntrySubmit(event) {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector("button");
    button.classList.add("is-loading");
    const result = await postForm(form);
    button.classList.remove("is-loading");

    if (!result.ok) {
        window.alert(result.error || "Could not clear this entry.");
        return;
    }
    removeBookRow(form.querySelector('input[name="book_id"]').value);
}

async function handleClearAllSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector("button");
    button.classList.add("is-loading");
    const result = await postForm(form);
    button.classList.remove("is-loading");

    if (!result.ok) {
        window.alert(result.error || "Could not clear these entries.");
        return;
    }

    const tabPane = form.closest(".tab-pane");
    (result.book_ids || []).forEach(removeBookRow);
    if (tabPane) showEmptyStateIfNeeded(tabPane);
}

function wireUpJobForms() {
    document.querySelectorAll(".abandon-form").forEach(form => {
        form.addEventListener("submit", handleAbandonSubmit);
    });
    document.querySelectorAll(".clear-entry-form").forEach(form => {
        form.addEventListener("submit", handleClearEntrySubmit);
    });
    document.querySelectorAll(".clear-all-form").forEach(form => {
        form.addEventListener("submit", handleClearAllSubmit);
    });
}

function updateStuckWarning(bookId, data) {
    const warning = document.getElementById(`stuck-${bookId}`);
    if (!warning) return;

    if (!data.stuck) {
        warning.style.display = "none";
        return;
    }

    const message = warning.querySelector(".stuck-message");
    if (message) {
        message.textContent = data.worker_alive
            ? "A worker is running but hasn't picked up this job yet — it may be backlogged."
            : "No worker responded to a health check — it may be down, or just unreachable over the queue.";
    }
    warning.style.display = "";
}

async function pollProcessingBooks() {
    if (document.visibilityState === "hidden") return;

    const rows = document.querySelectorAll("[data-poll-book]");
    for (const row of rows) {
        const bookId = row.dataset.pollBook;
        try {
            const response = await fetch(row.dataset.statusUrl);
            if (!response.ok) continue;
            const data = await response.json();

            // The row may have been removed locally (e.g. abandoned) while
            // this request was in flight; don't reload on its behalf.
            if (!row.isConnected) continue;

            if (data.status !== "Processing") {
                // Book moved to another tab (done/error/abandoned);
                // refresh so it's rendered in the right place
                location.reload();
                return;
            }

            const progress = document.getElementById(`progress-${bookId}`);
            if (progress) {
                progress.value = data.progress_percent;
                progress.textContent = `${data.progress_percent}%`;
            }
            const stage = document.getElementById(`stage-${bookId}`);
            if (stage) {
                stage.textContent = data.stage || "Queued";
            }
            updateStuckWarning(bookId, data);
        } catch (error) {
            // Server temporarily unreachable; try again next tick
        }
    }
}

window.addEventListener('load', function () {
    const defaultTab = document.querySelector(".tabs").dataset.default
    openTab(defaultTab);
    wireUpJobForms();

    if (document.querySelectorAll("[data-poll-book]").length > 0) {
        setInterval(pollProcessingBooks, 3000);
    }
});
