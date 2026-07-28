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

async function pollProcessingBooks() {
    if (document.visibilityState === "hidden") return;

    const rows = document.querySelectorAll("[data-poll-book]");
    for (const row of rows) {
        const bookId = row.dataset.pollBook;
        try {
            const response = await fetch(row.dataset.statusUrl);
            if (!response.ok) continue;
            const data = await response.json();

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
        } catch (error) {
            // Server temporarily unreachable; try again next tick
        }
    }
}

window.addEventListener('load', function () {
    const defaultTab = document.querySelector(".tabs").dataset.default
    openTab(defaultTab);

    if (document.querySelectorAll("[data-poll-book]").length > 0) {
        setInterval(pollProcessingBooks, 3000);
    }
});
