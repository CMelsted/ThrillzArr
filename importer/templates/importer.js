{% load static %}
const IMPORT_URL = "{% url 'import' %}";
const COVER_PLACEHOLDER_URL = "{% static 'images/cover_not_available.jpg' %}";

function expandFolder(folderId) {
    // Select the arrow element
    const arrow = document.querySelector(`.folder[id^='${folderId}'] .arrow i`);

    // Toggle the rotation class on the arrow element
    arrow.classList.toggle('fa-rotate-90');

    // Select all items in the folder
    const items = document.querySelectorAll(`.panel-block[folder-id^='${folderId}']`);

    // Toggle the display style of each item
    items.forEach(item => {
        item.style.display = item.style.display === 'none' ? '' : 'none';
    });
}

const arrows = document.querySelectorAll(".arrow i");
arrows.forEach(arrow => {
    arrow.addEventListener("click", (event) => {
        event.preventDefault();
        expandFolder(arrow.id)
    });
});

function showMatchError(message) {
    const banner = document.getElementById("match-error");
    banner.textContent = message;
    banner.style.display = message ? "block" : "none";
}

async function postAction(payload) {
    const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
    const body = new URLSearchParams({ csrfmiddlewaretoken: csrfToken, ...payload });

    try {
        const response = await fetch(IMPORT_URL, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body: body,
        });
        return await response.json();
    } catch (error) {
        return { ok: false, error: `Could not reach the server: ${error}` };
    }
}

function findTreeRow(srcPath) {
    return Array.from(document.querySelectorAll('[data-src-path]'))
        .find(el => el.dataset.srcPath === srcPath);
}

function updateMatchSectionVisibility() {
    const container = document.getElementById("match-entries-container");
    document.getElementById("match-section").style.display =
        container.children.length ? "" : "none";
}

// --- Moving an item from the tree into the match area ---

async function importEntry(srcPath, rowEl) {
    const button = rowEl.querySelector("button");
    button.classList.add("is-loading");
    const result = await postAction({ action: "add", src_path: srcPath });
    button.classList.remove("is-loading");

    if (!result.ok) {
        showMatchError(result.error);
        return;
    }
    showMatchError("");

    rowEl.classList.add("is-imported-hidden");

    const label = srcPath.split("/").filter(Boolean).pop() || srcPath;
    const counter = nextMatchCounter++;
    const entry = buildMatchEntry(counter, srcPath, label);
    document.getElementById("match-entries-container").appendChild(entry);
    updateMatchSectionVisibility();

    await fetchOptionsForSelect(document.getElementById(`asin-select-${counter}`));
    checkAllSelectsHaveValue();
}

function buildMatchEntry(counter, srcPath, label) {
    const wrapper = document.createElement("div");
    wrapper.className = "column is-grouped";
    wrapper.id = `asin-search-${counter}`;

    const headerRow = document.createElement("div");
    headerRow.className = "is-flex is-align-items-center";
    headerRow.style.gap = "15px";

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "button is-danger is-rounded remove-entry";
    removeButton.title = "Remove this item";
    removeButton.innerHTML = '<span class="icon"><i class="fas fa-times"></i></span>';
    removeButton.addEventListener("click", () => openRemoveConfirmationModal(srcPath, String(counter)));
    headerRow.appendChild(removeButton);

    const imageLabelContainer = document.createElement("div");
    imageLabelContainer.className = "image-label-container";

    const img = document.createElement("img");
    img.src = COVER_PLACEHOLDER_URL;
    img.id = `image-${counter}`;
    imageLabelContainer.appendChild(img);

    const labelEl = document.createElement("label");
    labelEl.className = "label";
    labelEl.textContent = label;
    imageLabelContainer.appendChild(labelEl);

    headerRow.appendChild(imageLabelContainer);
    wrapper.appendChild(headerRow);

    const field = document.createElement("div");
    field.className = "field is-flex is-flex-direction-column";

    const control = document.createElement("div");
    control.className = "control is-inline-flex is-align-items-center";

    const selectWrap = document.createElement("div");
    selectWrap.className = "select is-loading mr-3 is-fullwidth";

    const select = document.createElement("select");
    select.className = "asin-select";
    select.id = `asin-select-${counter}`;
    select.name = "asin";
    select.dataset.srcPath = srcPath;
    const initialOption = document.createElement("option");
    initialOption.textContent = srcPath;
    select.appendChild(initialOption);
    select.addEventListener("change", () => {
        updateImage(String(counter));
        checkSelectHasValue(String(counter));
    });
    selectWrap.appendChild(select);
    control.appendChild(selectWrap);

    const searchButton = document.createElement("button");
    searchButton.className = "button is-link";
    searchButton.type = "button";
    searchButton.textContent = "Custom Search";
    searchButton.addEventListener("click", () => openSearchPanel(srcPath, select.id));
    control.appendChild(searchButton);

    const acceptButton = document.createElement("button");
    acceptButton.className = "button is-success ml-2";
    acceptButton.type = "button";
    acceptButton.id = `accept-${counter}`;
    acceptButton.disabled = true;
    acceptButton.innerHTML = '<span class="icon"><i class="fas fa-check"></i></span><span>Accept</span>';
    acceptButton.addEventListener("click", () => acceptEntry(String(counter)));
    control.appendChild(acceptButton);

    field.appendChild(control);
    wrapper.appendChild(field);

    return wrapper;
}

// --- Custom search / remove-confirmation modals ---

function openSearchPanel(srcPath, select_id) {
    const modal = document.getElementById('custom-search-modal');
    const modalTitle = modal.querySelector('.modal-card-title');
    modalTitle.textContent = `Custom Search: ${srcPath}`;
    modal.classList.add('is-active');
    modal.dataset.value = select_id;
}

function closeSearchPanel() {
    const modal = document.getElementById('custom-search-modal');

    // Clear the input fields
    modal.querySelector('#title').value = '';
    modal.querySelector('#author').value = '';
    modal.querySelector('#keywords').value = '';

    // Clear the search notification
    document.getElementById('search-notification').style.display = "none";

    // Close the panel
    modal.classList.remove("is-active");
}

function openRemoveConfirmationModal(label, counter) {
    const modalLabel = document.querySelector("#confirm-modal-title");
    modalLabel.textContent = `Remove ${label} from search`;

    const modalButton = document.querySelector("#remove-column-button");
    modalButton.onclick = () => removeColumn(counter)

    // Get the modal element and set it to active
    const modal = document.getElementById('remove-confirmation-modal');
    modal.classList.add('is-active');
}

function closeRemoveConfirmationModal() {
    // Get the modal element and remove the active class
    const modal = document.getElementById('remove-confirmation-modal');
    modal.classList.remove('is-active');
}

// --- Accept / remove, driven through the same endpoint as Import ---

async function postEntry(counter, action) {
    const select = document.getElementById(`asin-select-${counter}`);
    const payload = { src_path: select.dataset.srcPath };
    if (action === "remove") {
        payload.action = "remove";
    } else {
        payload.asin = select.value;
    }
    return postAction(payload);
}

// Returns false when the caller should stop (error, or we're navigating)
function applyResult(counter, result) {
    if (!result.ok) {
        showMatchError(result.error);
        return false;
    }

    showMatchError("");
    document.querySelector(`#asin-search-${counter}`).remove();
    updateMatchSectionVisibility();

    if (result.url) {
        window.location.href = result.url;
        return false;
    }
    return true;
}

async function acceptEntry(counter) {
    const button = document.getElementById(`accept-${counter}`);
    button.classList.add("is-loading");
    const result = await postEntry(counter, "accept");
    button.classList.remove("is-loading");
    applyResult(counter, result);
}

async function acceptAll() {
    const button = document.getElementById("accept-all");
    button.classList.add("is-loading");

    let skipped = 0;
    for (const select of Array.from(document.querySelectorAll(".asin-select"))) {
        if (select.value.length !== 10) {
            skipped++;
            continue;
        }
        const counter = select.id.split("-").pop();
        const result = await postEntry(counter, "accept");
        if (!applyResult(counter, result)) {
            break;
        }
    }

    button.classList.remove("is-loading");
    if (skipped) {
        showMatchError(`${skipped} book(s) still need a match before they can be accepted.`);
    }
}

async function removeColumn(counter) {
    closeRemoveConfirmationModal();
    const select = document.getElementById(`asin-select-${counter}`);
    const srcPath = select ? select.dataset.srcPath : null;

    const result = await postEntry(counter, "remove");
    const ok = applyResult(counter, result);

    if (ok && srcPath) {
        const row = findTreeRow(srcPath);
        if (row) {
            row.classList.remove("is-imported-hidden");
        }
    }
}

// --- ASIN auto-search ---

function constructQueryParams(media_dir, title, author, keywords) {
    let params = [];
    if (media_dir) {
        params.push(`media_dir=${encodeURIComponent(media_dir)}`);
    }
    if (title) {
        params.push(`title=${encodeURIComponent(title)}`);
    }
    if (author) {
        params.push(`author=${encodeURIComponent(author)}`);
    }
    if (keywords) {
        params.push(`keywords=${encodeURIComponent(keywords)}`);
    }
    return `?${params.join('&')}`;
}

async function search(url) {
    try {
        const response = await fetch(url);
        const data = response.json();
        return data;

    } catch (error) {
        console.error(`Error fetching options for select with url ${url}: ${error}`);
    }
}

function createOption(value, text, image_link) {
    const opt = document.createElement("option");
    if (value) {
        opt.value = value;
    }

    opt.text = text;
    opt.setAttribute("data-image-link", image_link);
    return opt;
}

function noOptionsFound(select) {
    select.style.borderColor = "red";
    select.style.borderWidth = "2px";
    let opt = createOption("", "No Audiobook results found, try a custom search...", "");
    select.appendChild(opt);
}

function updateOptions(select, data) {
    select.innerHTML = "";

    if (!data.length) {
        noOptionsFound(select);
        select.parentElement.classList.remove("is-loading");
        return;
    }

    select.removeAttribute("style");

    data.forEach(option => {
        text = option.title + " by " + option.author + " - Narrator " + option.narrator + ": " + option.asin;
        let opt = createOption(option.asin, text, option.image_link);
        select.appendChild(opt);
    });

    select.parentElement.classList.remove("is-loading");
}

function updateImage(counter) {
    // Get the selected value from the select element
    const selectElement = document.getElementById(`asin-select-${counter}`);

    // Get the corresponding image element
    const imageElement = document.getElementById(`image-${counter}`);

    // Update the image source
    let image_link = selectElement.options[selectElement.selectedIndex].dataset.imageLink;

    if (image_link) {
        imageElement.src = image_link;
    }
}

function checkSelectHasValue(counter) {
    const select = document.getElementById(`asin-select-${counter}`);
    const acceptButton = document.getElementById(`accept-${counter}`);
    acceptButton.disabled = select.value.length != 10;
}

function checkAllSelectsHaveValue() {
    document.querySelectorAll(".asin-select").forEach(select => {
        checkSelectHasValue(select.id.split('-').pop());
    });
}

async function searchAsin(title, author, keywords) {
    const modal = document.getElementById('custom-search-modal');
    const select = document.getElementById(modal.dataset.value);

    // Build the query params and url
    let queryParams = constructQueryParams("", title, author, keywords);
    console.debug(queryParams);
    url = "asin-search" + queryParams;

    // Call the URL and get response
    let data = await search(url);

    if (!data.length) {
        // display message in search panel and return, dont close the search panel
        document.getElementById('search-notification').style.display = "block";
        return;
    }

    // Update the select for the calling custom search
    updateOptions(select, data)

    // update cover image
    const counter = select.id.split('-').pop();
    updateImage(counter)

    // close the search panel
    closeSearchPanel();

    // check all selects have a value and update submit button
    checkAllSelectsHaveValue();
}

async function fetchOptionsForSelect(select) {
    const url = "asin-search" + constructQueryParams(select.dataset.srcPath.split('/').pop());
    const data = await search(url);
    updateOptions(select, data);
    updateImage(select.id.split('-').pop());
}

async function fetchOptions() {
    const selects = document.querySelectorAll(".asin-select");
    await Promise.all(Array.from(selects).map(fetchOptionsForSelect));
    checkAllSelectsHaveValue();
}

let nextMatchCounter = document.querySelectorAll(".asin-select").length;
if (nextMatchCounter > 0) {
    fetchOptions();
    checkAllSelectsHaveValue();
}
