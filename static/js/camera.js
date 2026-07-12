function setText(root, selector, text) {
    const element = root.querySelector(selector);
    if (!element) {
        return;
    }
    element.textContent = text || "";
}

function setDirectPill(root, selector, payload) {
    const element = root.querySelector(selector);
    if (!element || !payload) {
        return;
    }
    element.textContent = payload.label || "";
    element.dataset.status = payload.status || "unknown";
    element.title = payload.message || "";
}

export function applyCameraPreviewPayload(root, payload) {
    const overlay = root.querySelector("[data-camera-preview-overlay]");
    if (!overlay || !payload) {
        return;
    }

    overlay.dataset.status = payload.status || "unknown";
    setText(root, "[data-camera-preview-title]", payload.title || "");
    setText(root, "[data-camera-preview-copy]", payload.message || "");

    if (payload.show_placeholder) {
        overlay.hidden = false;
        overlay.classList.remove("camera-preview-overlay-hidden");
        return;
    }

    overlay.hidden = true;
    overlay.classList.add("camera-preview-overlay-hidden");
}

export function applyCameraAnalysisPayload(root, payload) {
    if (!payload || typeof payload !== "object") {
        return;
    }
    setDirectPill(root, "[data-camera-analysis='autofocus']", payload.autofocus);
    setDirectPill(root, "[data-camera-analysis='lighting']", payload.lighting);
    setDirectPill(root, "[data-camera-analysis='sharpness']", payload.sharpness);
}

export function initLivePreview(root) {
    const previewImage = root.querySelector("[data-live-preview-image]");
    if (!previewImage) {
        return;
    }

    previewImage.addEventListener("error", () => {
        applyCameraPreviewPayload(root, {
            status: "fail",
            title: "Camera unavailable",
            message: "The live preview could not be loaded.",
            show_placeholder: true,
        });
    });

    const refreshMs = Number(previewImage.dataset.livePreviewRefreshMs || "0");
    const baseUrl = previewImage.dataset.livePreviewBaseUrl || "";
    if (!baseUrl || refreshMs <= 0) {
        return;
    }

    let previewRequestInFlight = false;
    let previewRefreshTimer = null;
    let previewObjectUrl = "";

    const refreshPreview = () => {
        if (previewRequestInFlight) {
            return;
        }
        previewRequestInFlight = true;

        fetch(`${baseUrl}?t=${Date.now()}`, {
            cache: "no-store",
            headers: {
                Accept: "image/jpeg",
            },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Preview request failed");
                }
                return response.blob();
            })
            .then((blob) => {
                if (previewObjectUrl) {
                    window.URL.revokeObjectURL(previewObjectUrl);
                }
                previewObjectUrl = window.URL.createObjectURL(blob);
                previewImage.src = previewObjectUrl;
            })
            .catch(() => {
                applyCameraPreviewPayload(root, {
                    status: "fail",
                    title: "Camera unavailable",
                    message: "The live preview could not be refreshed.",
                    show_placeholder: true,
                });
            })
            .finally(() => {
                previewRequestInFlight = false;
                previewRefreshTimer = window.setTimeout(refreshPreview, refreshMs);
            });
    };

    refreshPreview();

    window.addEventListener("beforeunload", () => {
        if (previewRefreshTimer) {
            window.clearTimeout(previewRefreshTimer);
        }
        if (previewObjectUrl) {
            window.URL.revokeObjectURL(previewObjectUrl);
        }
    });
}
