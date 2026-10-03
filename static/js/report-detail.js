document.addEventListener("DOMContentLoaded", function () {
    // 1. Initialize detail mini map
    const coordsEl = document.getElementById("report-coords");
    const mapEl = document.getElementById("detail-map");

    if (coordsEl && mapEl && typeof L !== "undefined") {
        const rawLat = coordsEl.getAttribute("data-lat");
        const rawLng = coordsEl.getAttribute("data-lng");
        const status = coordsEl.getAttribute("data-status") || "Submitted";
        const lat = parseFloat(rawLat);
        const lng = parseFloat(rawLng);

        if (!isNaN(lat) && !isNaN(lng) && isFinite(lat) && isFinite(lng)) {
            try {
                const detailMap = L.map('detail-map').setView([lat, lng], 15);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
                    maxZoom: 19
                }).addTo(detailMap);

                function createPinIcon(statusText) {
                    let color = '#2563eb';
                    if (statusText === 'Resolved' || statusText === 'Closed') {
                        color = '#16a34a';
                    } else if (statusText === 'In Progress' || statusText === 'Assigned' || statusText === 'Under Review') {
                        color = '#d97706';
                    } else if (statusText === 'Submitted' || statusText === 'Reopened') {
                        color = '#dc2626';
                    }
                    return L.divIcon({
                        className: 'custom-map-pin',
                        html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 42" width="32" height="42" style="filter: drop-shadow(0 3px 5px rgba(0,0,0,0.35));"><path fill="${color}" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M16 1C8.268 1 2 7.268 2 15c0 10.5 14 25.5 14 25.5S30 25.5 30 15c0-7.732-6.268-14-14-14z"/><circle cx="16" cy="15" r="5.5" fill="#ffffff"/></svg>`,
                        iconSize: [32, 42],
                        iconAnchor: [16, 42],
                        popupAnchor: [0, -38]
                    });
                }

                L.marker([lat, lng], { icon: createPinIcon(status) }).addTo(detailMap);
            } catch (err) {
                console.error("Failed to render detail map:", err);
            }
        }
    }

    // 2. Rich Text Editor Toolbar and Syncing
    const editor = document.getElementById("comment-editor");
    const contentInput = document.getElementById("content");
    const commentForm = document.getElementById("comment-form");
    const toolbarButtons = document.querySelectorAll(".toolbar-btn");

    function syncContent() {
        if (!editor || !contentInput) return;
        const html = editor.innerHTML.trim();
        const text = editor.innerText.trim();
        if (text === "" && (html === "" || html === "<br>" || html === "<p></p>")) {
            contentInput.value = "";
        } else {
            contentInput.value = html;
        }
    }

    if (toolbarButtons && editor) {
        toolbarButtons.forEach(function (button) {
            button.addEventListener("click", function (e) {
                e.preventDefault();
                const command = button.getAttribute("data-command");
                const value = button.getAttribute("data-value") || null;
                document.execCommand(command, false, value);
                editor.focus();
                syncContent();
            });
        });
    }

    if (editor) {
        editor.addEventListener("input", syncContent);
        editor.addEventListener("blur", syncContent);
        editor.addEventListener("keyup", syncContent);
    }

    if (commentForm) {
        commentForm.addEventListener("submit", function (e) {
            syncContent();
            const textContent = editor ? (editor.innerText || editor.textContent || "").trim() : "";
            const val = contentInput ? contentInput.value.trim() : "";

            if (!val || !textContent) {
                e.preventDefault();
                alert("Please enter a comment before submitting.");
                if (editor) editor.focus();
                return false;
            }
        });
    }
});
