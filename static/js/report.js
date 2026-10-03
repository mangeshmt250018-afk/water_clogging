document.addEventListener("DOMContentLoaded", function () {
    const causeSelect = document.querySelector('select[name="cause"]');
    if (causeSelect && causeSelect.options.length) {
        causeSelect.options[0].disabled = true;
    }

    const latField = document.getElementById("latitude");
    const lngField = document.getElementById("longitude");
    const form = document.querySelector("form");
    const statusContainer = document.getElementById("location-status-container");
    const statusTitle = document.getElementById("location-status-title");
    const statusText = document.getElementById("location-status-text");
    const retryBtn = document.getElementById("retry-location-btn");
    const helpText = document.getElementById("location-help-text");
    const iconSpan = document.getElementById("location-icon");

    let isLocationAcquired = false;
    let isRequestInProgress = false;

    function showStatus(type, title, message, help, canRetry) {
        if (!statusContainer) return;
        statusContainer.classList.remove("hidden");

        if (type === "success") {
            statusContainer.className = "mb-4 p-4 rounded-2xl bg-green-50 border border-green-200 text-green-800 transition-all";
            if (iconSpan) iconSpan.textContent = "✅";
        } else if (type === "error") {
            statusContainer.className = "mb-4 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 transition-all";
            if (iconSpan) iconSpan.textContent = "⚠️";
        } else if (type === "info") {
            statusContainer.className = "mb-4 p-4 rounded-2xl bg-blue-50 border border-blue-200 text-blue-800 transition-all";
            if (iconSpan) iconSpan.textContent = "📍";
        }

        if (statusTitle) statusTitle.textContent = title;
        if (statusText) statusText.textContent = message;

        if (helpText) {
            if (help) {
                helpText.textContent = help;
                helpText.classList.remove("hidden");
            } else {
                helpText.classList.add("hidden");
            }
        }

        if (retryBtn) {
            if (canRetry) {
                retryBtn.classList.remove("hidden");
            } else {
                retryBtn.classList.add("hidden");
            }
        }
    }

    function requestLocation() {
        if (isRequestInProgress) return;

        if (!navigator.geolocation) {
            showStatus(
                "error",
                "Geolocation Not Supported",
                "Your browser does not support automatic location detection.",
                "Please use a modern browser such as Chrome, Firefox, Safari, or Edge.",
                false
            );
            return;
        }

        isRequestInProgress = true;
        showStatus(
            "info",
            "Acquiring Location...",
            "Please allow the browser permission prompt to detect your current coordinates.",
            null,
            false
        );

        navigator.geolocation.getCurrentPosition(
            function (position) {
                isRequestInProgress = false;
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                if (latField) latField.value = latitude;
                if (lngField) lngField.value = longitude;
                isLocationAcquired = true;

                showStatus(
                    "success",
                    "Location Acquired",
                    `Coordinates: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`,
                    null,
                    false
                );
            },
            function (error) {
                isRequestInProgress = false;
                isLocationAcquired = false;
                if (latField) latField.value = "";
                if (lngField) lngField.value = "";

                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        showStatus(
                            "error",
                            "Location Permission Denied",
                            "Location permission is required to accurately map water clogging reports.",
                            "If you blocked location access, click the lock/settings icon in your browser address bar to allow location permissions, then click 'Retry Location'.",
                            true
                        );
                        break;
                    case error.POSITION_UNAVAILABLE:
                        showStatus(
                            "error",
                            "Location Unavailable",
                            "Your device could not determine your current position.",
                            "Ensure GPS/location services are enabled on your device, then click 'Retry Location'.",
                            true
                        );
                        break;
                    case error.TIMEOUT:
                        showStatus(
                            "error",
                            "Location Request Timed Out",
                            "The location request took too long to respond.",
                            "Check your network and GPS connection, then click 'Retry Location'.",
                            true
                        );
                        break;
                    default:
                        showStatus(
                            "error",
                            "Location Error",
                            "An unexpected error occurred while detecting location.",
                            "Please click 'Retry Location' to try again.",
                            true
                        );
                        break;
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }

    if (retryBtn) {
        retryBtn.addEventListener("click", function () {
            requestLocation();
        });
    }

    // Intercept form submission to guarantee coordinates exist without erasing form inputs
    if (form) {
        form.addEventListener("submit", function (e) {
            const currentLat = latField ? latField.value.trim() : "";
            const currentLng = lngField ? lngField.value.trim() : "";

            if (!currentLat || !currentLng || !isLocationAcquired) {
                e.preventDefault();
                showStatus(
                    "error",
                    "Location Required",
                    "Cannot submit report without location coordinates. Please grant location access.",
                    "Click 'Retry Location' to prompt your browser for location permission.",
                    true
                );
                if (statusContainer) {
                    statusContainer.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            }
        });
    }

    // Trigger location detection on page load
    requestLocation();
});
