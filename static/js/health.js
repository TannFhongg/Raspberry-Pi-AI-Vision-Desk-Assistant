import { applyCameraAnalysisPayload, applyCameraPreviewPayload } from "./camera.js";

function setPill(root, selector, payload) {
    const element = root.querySelector(selector);
    if (!element || !payload) {
        return;
    }
    element.textContent = element.dataset.label || payload.label || "";
    element.dataset.status = payload.status || "unknown";
    element.title = payload.message || "";
}

export function initHealthPolling(root) {
    const healthUrl = root.dataset.healthUrl || "";
    const healthPollMs = Number(root.dataset.healthPollMs || "0");
    if (!healthUrl || healthPollMs <= 0 || !root.querySelector("[data-health-bar]")) {
        return;
    }

    let healthRequestInFlight = false;

    const applyHealthPayload = (payload) => {
        if (!payload || typeof payload !== "object") {
            return;
        }
        setPill(root, "[data-health-overall]", payload.overall);
        setPill(root, "[data-health-cpu]", payload.cpu);
        setPill(root, "[data-health-memory]", payload.memory);
        setPill(root, "[data-health-network]", payload.network);
        setPill(root, "[data-health-camera]", payload.camera);
        applyCameraPreviewPayload(root, payload.camera_preview);
        applyCameraAnalysisPayload(root, payload.camera_analysis);
    };

    const pollHealth = () => {
        if (healthRequestInFlight) {
            return;
        }
        healthRequestInFlight = true;

        fetch(healthUrl, {
            cache: "no-store",
            headers: {
                Accept: "application/json",
            },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Health request failed");
                }
                return response.json();
            })
            .then(applyHealthPayload)
            .catch(() => null)
            .finally(() => {
                healthRequestInFlight = false;
            });
    };

    pollHealth();
    window.setInterval(pollHealth, healthPollMs);
}
