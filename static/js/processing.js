function setText(root, selector, text) {
    const element = root.querySelector(selector);
    if (!element) {
        return;
    }
    element.textContent = text || "";
}

export function applyProcessingStatePayload(root, payload) {
    setText(root, "[data-processing-title]", payload.processing_title || "");
    setText(root, "[data-processing-subtitle]", payload.processing_subtitle || "");
    setText(root, "[data-processing-status-text]", payload.processing_status_message || payload.display_status || "");

    const modeElement = root.querySelector("[data-processing-mode-value]");
    if (modeElement) {
        modeElement.textContent = payload.processing_mode_label || "";
    }

    const statusCard = root.querySelector("[data-processing-status-card]");
    if (statusCard) {
        statusCard.dataset.status = payload.processing_status_tone || "active";
    }

    const stepElements = root.querySelectorAll(".processing-progress-step");
    const progressSteps = Array.isArray(payload.progress_steps) ? payload.progress_steps : [];
    for (let index = 0; index < stepElements.length; index += 1) {
        const stepElement = stepElements[index];
        const stepPayload = progressSteps[index];
        if (!stepPayload) {
            continue;
        }

        stepElement.className =
            `processing-progress-step processing-progress-step-${stepPayload.state} ` +
            `progress-step progress-step-${stepPayload.state}`;

        const indicatorElement = stepElement.querySelector(".processing-progress-indicator");
        if (indicatorElement) {
            indicatorElement.setAttribute("aria-label", stepPayload.state_label || "");
        }

        const labelElement = stepElement.querySelector(".processing-progress-label");
        if (labelElement) {
            labelElement.textContent = stepPayload.label || "";
        }
    }
}

export function initUiStatePolling(root) {
    const currentScreen = root.dataset.currentScreen || "";
    const uiStateUrl = root.dataset.uiStateUrl || "";
    const uiStatePollMs = Number(root.dataset.uiStatePollMs || "0");
    if (!uiStateUrl || uiStatePollMs <= 0) {
        return;
    }

    let latestUiState = root.dataset.uiStateUpdatedAt || "";
    let uiStateRequestInFlight = false;

    const applyUiStatePayload = (payload) => {
        if (!payload || typeof payload !== "object" || !payload.updated_at) {
            return;
        }
        if (payload.updated_at === latestUiState) {
            return;
        }
        if (currentScreen === "processing" && payload.screen === "processing") {
            latestUiState = payload.updated_at;
            root.dataset.uiStateUpdatedAt = latestUiState;
            applyProcessingStatePayload(root, payload);
            return;
        }
        window.location.reload();
    };

    window.setInterval(() => {
        if (uiStateRequestInFlight) {
            return;
        }
        uiStateRequestInFlight = true;

        fetch(uiStateUrl, {
            cache: "no-store",
            headers: {
                Accept: "application/json",
            },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("UI state request failed");
                }
                return response.json();
            })
            .then(applyUiStatePayload)
            .catch(() => null)
            .finally(() => {
                uiStateRequestInFlight = false;
            });
    }, uiStatePollMs);
}
