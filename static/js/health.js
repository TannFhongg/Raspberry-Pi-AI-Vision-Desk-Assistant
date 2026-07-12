import { applyCameraAnalysisPayload, applyCameraPreviewPayload } from "./camera.js";

const METRIC_STATES = ["healthy", "warning", "error", "unavailable"];
const VALUE_SIZE_CLASSES = ["normal", "long", "very-long"];
const UNAVAILABLE_AFTER_ERRORS = 3;
const MAX_BACKOFF_MS = 30000;

function normalizeState(state) {
    return METRIC_STATES.includes(state) ? state : "unavailable";
}

function classifyValueSize(value) {
    const normalizedValue = String(value || "N/A").replace(/\s+/g, "");
    if (normalizedValue.length >= 10) {
        return "very-long";
    }
    if (normalizedValue.length >= 8) {
        return "long";
    }
    return "normal";
}

function normalizeValueSize(valueSize, value) {
    if (VALUE_SIZE_CLASSES.includes(valueSize)) {
        return valueSize;
    }
    return classifyValueSize(value);
}

function setMetric(root, payload) {
    const key = payload?.key || "";
    const element = key ? root.querySelector(`[data-health-pill-key="${key}"]`) : null;
    if (!element) {
        return;
    }

    const state = normalizeState(payload.state);
    const valueElement = element.querySelector("[data-health-value]");
    if (valueElement) {
        const value = payload.value || "N/A";
        const valueSize = normalizeValueSize(payload.value_size, value);
        valueElement.textContent = value;
        VALUE_SIZE_CLASSES.forEach((sizeClass) => {
            valueElement.classList.remove(`health-pill__value--${sizeClass}`);
        });
        valueElement.classList.add(`health-pill__value--${valueSize}`);
    }

    METRIC_STATES.forEach((metricState) => {
        element.classList.remove(`health-pill--${metricState}`);
    });
    element.classList.add(`health-pill--${state}`);
    element.dataset.healthState = state;
    element.title = payload.title || payload.message || "";
    element.setAttribute("aria-label", payload.aria_label || `${payload.label || key}: ${payload.value || "N/A"}`);
}

function extractMetrics(payload) {
    if (!payload || typeof payload !== "object") {
        return [];
    }

    if (Array.isArray(payload.metrics)) {
        return payload.metrics;
    }

    const legacyMetricMap = {
        system: "system",
        cpu: "cpu",
        ram: "ram",
        wifi: "wifi",
        camera: "camera",
        overall: "system",
        memory: "ram",
        network: "wifi",
    };

    return Object.entries(legacyMetricMap)
        .map(([payloadKey, metricKey]) => {
            const metric = payload[payloadKey];
            if (!metric || typeof metric !== "object") {
                return null;
            }
            return {
                ...metric,
                key: metric.key || metricKey,
                value: metric.value || metric.label || "N/A",
                state: metric.state || metric.status || "unavailable",
                title: metric.title || metric.message || "",
                aria_label: metric.aria_label || `${metricKey.toUpperCase()}: ${metric.value || metric.label || "N/A"}`,
            };
        })
        .filter(Boolean);
}

function buildUnavailableMetrics() {
    return [
        {
            key: "system",
            label: "SYS",
            value: "WARNING",
            state: "warning",
            title: "Live header updates are temporarily unavailable. Retrying in the background.",
            aria_label: "System status: warning",
        },
        {
            key: "cpu",
            label: "CPU",
            value: "N/A",
            state: "unavailable",
            title: "CPU temperature is temporarily unavailable.",
            aria_label: "CPU temperature unavailable",
        },
        {
            key: "ram",
            label: "RAM",
            value: "N/A",
            state: "unavailable",
            title: "RAM usage is temporarily unavailable.",
            aria_label: "RAM usage unavailable",
        },
        {
            key: "wifi",
            label: "WIFI",
            value: "N/A",
            state: "unavailable",
            title: "Wi-Fi status is temporarily unavailable.",
            aria_label: "Wi-Fi status unavailable",
        },
        {
            key: "camera",
            label: "CAM",
            value: "N/A",
            state: "unavailable",
            title: "Camera status is temporarily unavailable.",
            aria_label: "Camera status unavailable",
        },
    ];
}

export function initHealthPolling(root) {
    const healthUrl = root.dataset.healthUrl || "";
    const healthPollMs = Number(root.dataset.healthPollMs || "0");
    if (!healthUrl || healthPollMs <= 0 || !root.querySelector("[data-health-bar]")) {
        return;
    }

    let healthRequestInFlight = false;
    let healthFailureCount = 0;
    let pollTimeoutId = 0;

    const applyHealthPayload = (payload) => {
        const metrics = extractMetrics(payload);
        if (!metrics.length) {
            throw new Error("Health payload missing metrics");
        }

        metrics.forEach((metric) => {
            setMetric(root, metric);
        });
        applyCameraPreviewPayload(root, payload.camera_preview);
        applyCameraAnalysisPayload(root, payload.camera_analysis);
    };

    const scheduleNextPoll = (delayMs) => {
        pollTimeoutId = window.setTimeout(pollHealth, Math.max(healthPollMs, delayMs));
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
            .then((payload) => {
                applyHealthPayload(payload);
                healthFailureCount = 0;
                scheduleNextPoll(healthPollMs);
            })
            .catch(() => {
                healthFailureCount += 1;
                if (healthFailureCount >= UNAVAILABLE_AFTER_ERRORS) {
                    buildUnavailableMetrics().forEach((metric) => {
                        setMetric(root, metric);
                    });
                }

                const retryDelay = Math.min(
                    healthPollMs * (2 ** Math.max(0, healthFailureCount - 1)),
                    MAX_BACKOFF_MS,
                );
                scheduleNextPoll(retryDelay);
            })
            .finally(() => {
                healthRequestInFlight = false;
            });
    };

    pollHealth();
    window.addEventListener("beforeunload", () => {
        window.clearTimeout(pollTimeoutId);
    }, { once: true });
}
