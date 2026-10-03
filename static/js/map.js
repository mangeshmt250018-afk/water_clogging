// Initialize Leaflet map and render report markers securely with safe DOM APIs
document.addEventListener("DOMContentLoaded", function () {
    const mapElement = document.getElementById('map');
    if (!mapElement) {
        return;
    }

    if (typeof L === 'undefined') {
        console.error("Leaflet library (L) is not loaded.");
        return;
    }

    // Helper to generate reliable, high-resolution SVG map pins
    function createMapPin(status) {
        let color = '#2563eb'; // blue default
        if (status === 'Resolved' || status === 'Closed') {
            color = '#16a34a'; // green
        } else if (status === 'In Progress' || status === 'Assigned' || status === 'Under Review') {
            color = '#d97706'; // amber
        } else if (status === 'Submitted' || status === 'Reopened') {
            color = '#dc2626'; // red
        }

        const svgHtml = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 42" width="32" height="42" style="filter: drop-shadow(0 3px 5px rgba(0,0,0,0.35));">
                <path fill="${color}" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M16 1C8.268 1 2 7.268 2 15c0 10.5 14 25.5 14 25.5S30 25.5 30 15c0-7.732-6.268-14-14-14z"/>
                <circle cx="16" cy="15" r="5.5" fill="#ffffff"/>
            </svg>
        `;

        return L.divIcon({
            className: 'custom-map-pin',
            html: svgHtml,
            iconSize: [32, 42],
            iconAnchor: [16, 42],
            popupAnchor: [0, -38]
        });
    }

    try {
        const defaultLat = 18.5951153;
        const defaultLng = 73.7385763;
        const map = L.map('map').setView([defaultLat, defaultLng], 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(map);

        // Read and parse reports data securely from the JSON script container
        const reportsDataEl = document.getElementById('reports-data');
        if (!reportsDataEl || !reportsDataEl.textContent) {
            return;
        }

        let reports = [];
        try {
            reports = JSON.parse(reportsDataEl.textContent);
        } catch (jsonErr) {
            console.error("Failed to parse reports-data JSON:", jsonErr);
            return;
        }

        if (!Array.isArray(reports) || reports.length === 0) {
            return;
        }

        const validMarkers = [];

        reports.forEach(function (report) {
            try {
                if (!report || report.latitude === undefined || report.longitude === undefined || report.latitude === null || report.longitude === null) {
                    return;
                }

                const lat = typeof report.latitude === 'number' ? report.latitude : parseFloat(report.latitude);
                const lng = typeof report.longitude === 'number' ? report.longitude : parseFloat(report.longitude);

                if (isNaN(lat) || isNaN(lng) || !isFinite(lat) || !isFinite(lng)) {
                    return;
                }

                const statusText = report.status || 'Submitted';
                const marker = L.marker([lat, lng], { icon: createMapPin(statusText) }).addTo(map);
                validMarkers.push([lat, lng]);

                // Create popup content safely using DOM APIs (100% XSS Safe)
                const container = document.createElement('div');
                container.style.fontFamily = "'Outfit', sans-serif, system-ui";
                container.style.fontSize = '13px';
                container.style.lineHeight = '1.4';
                container.style.color = '#1f2937';
                container.style.minWidth = '200px';
                container.style.maxWidth = '260px';

                // Header container with Title and Status
                const headerDiv = document.createElement('div');
                headerDiv.style.display = 'flex';
                headerDiv.style.justifyContent = 'space-between';
                headerDiv.style.alignItems = 'center';
                headerDiv.style.marginBottom = '6px';

                const title = document.createElement('h3');
                title.style.margin = '0';
                title.style.color = '#1e3a8a';
                title.style.fontWeight = '700';
                title.style.fontSize = '15px';
                title.textContent = report.id ? `Report #${report.id}` : 'Water Clogging';
                headerDiv.appendChild(title);

                const statusBadge = document.createElement('span');
                statusBadge.textContent = statusText;
                statusBadge.style.fontSize = '11px';
                statusBadge.style.fontWeight = '600';
                statusBadge.style.padding = '2px 8px';
                statusBadge.style.borderRadius = '12px';

                if (statusText === 'Resolved' || statusText === 'Closed') {
                    statusBadge.style.backgroundColor = '#dcfce7';
                    statusBadge.style.color = '#166534';
                } else if (statusText === 'In Progress' || statusText === 'Assigned' || statusText === 'Under Review') {
                    statusBadge.style.backgroundColor = '#fef3c7';
                    statusBadge.style.color = '#92400e';
                } else {
                    statusBadge.style.backgroundColor = '#dbeafe';
                    statusBadge.style.color = '#1e40af';
                }
                headerDiv.appendChild(statusBadge);
                container.appendChild(headerDiv);

                // Reporter Information
                const authorP = document.createElement('p');
                authorP.style.margin = '0 0 4px 0';
                const authorStrong = document.createElement('strong');
                authorStrong.textContent = 'Reported by: ';
                authorP.appendChild(authorStrong);
                authorP.appendChild(document.createTextNode(report.author || 'Anonymous'));
                container.appendChild(authorP);

                // Cause
                const causeP = document.createElement('p');
                causeP.style.margin = '0 0 4px 0';
                const causeStrong = document.createElement('strong');
                causeStrong.textContent = 'Cause: ';
                causeP.appendChild(causeStrong);
                causeP.appendChild(document.createTextNode(report.cause || 'Unspecified'));
                container.appendChild(causeP);

                // Description (if present)
                if (report.description) {
                    const descP = document.createElement('p');
                    descP.style.margin = '0 0 6px 0';
                    descP.style.color = '#4b5563';
                    descP.textContent = report.description;
                    container.appendChild(descP);
                }

                // Image thumbnail (if present and valid URL)
                if (report.image_path) {
                    let validUrl = false;
                    try {
                        const parsed = new URL(report.image_path);
                        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
                            validUrl = true;
                        }
                    } catch (_) {}

                    if (validUrl) {
                        const imgDiv = document.createElement('div');
                        imgDiv.style.marginTop = '6px';
                        imgDiv.style.marginBottom = '8px';
                        const img = document.createElement('img');
                        img.src = report.image_path;
                        img.alt = 'Water clogging report photo';
                        img.style.width = '100%';
                        img.style.maxHeight = '140px';
                        img.style.objectFit = 'cover';
                        img.style.borderRadius = '8px';
                        img.loading = 'lazy';
                        imgDiv.appendChild(img);
                        container.appendChild(imgDiv);
                    }
                }

                // Action Link to Report Details
                if (report.id) {
                    const actionDiv = document.createElement('div');
                    actionDiv.style.marginTop = '8px';
                    actionDiv.style.textAlign = 'center';

                    const detailsLink = document.createElement('a');
                    detailsLink.href = `/report/${encodeURIComponent(report.id)}`;
                    detailsLink.textContent = 'View Report Details →';
                    detailsLink.style.display = 'inline-block';
                    detailsLink.style.width = '100%';
                    detailsLink.style.padding = '6px 12px';
                    detailsLink.style.backgroundColor = '#2563eb';
                    detailsLink.style.color = '#ffffff';
                    detailsLink.style.textDecoration = 'none';
                    detailsLink.style.borderRadius = '6px';
                    detailsLink.style.fontSize = '12px';
                    detailsLink.style.fontWeight = '600';
                    detailsLink.style.boxSizing = 'border-box';
                    detailsLink.style.transition = 'background-color 150ms';
                    detailsLink.onmouseover = function () { this.style.backgroundColor = '#1d4ed8'; };
                    detailsLink.onmouseout = function () { this.style.backgroundColor = '#2563eb'; };

                    actionDiv.appendChild(detailsLink);
                    container.appendChild(actionDiv);
                }

                marker.bindPopup(container);
            } catch (err) {
                console.error("Failed to render individual marker:", err);
            }
        });

        // Fit map view to bounds if markers exist
        if (validMarkers.length > 1) {
            const bounds = L.latLngBounds(validMarkers);
            map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
        } else if (validMarkers.length === 1) {
            map.setView(validMarkers[0], 14);
        }
    } catch (mapErr) {
        console.error("Leaflet map initialization error:", mapErr);
    }
});
