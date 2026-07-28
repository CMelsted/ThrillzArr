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

// add action to make the select all checkbox select/deselect all top level objects
const selectAllCheckbox = document.getElementById("select-all-checkbox");
const checkboxes = document.querySelectorAll('.panel-block-container label[folder-id=""] input[type="checkbox"]');
selectAllCheckbox.addEventListener("change", function () {
    checkboxes.forEach(function (checkbox) {
        checkbox.checked = selectAllCheckbox.checked;
    });
});
