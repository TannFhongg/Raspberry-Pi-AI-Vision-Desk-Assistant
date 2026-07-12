function fieldValue(field) {
    if (field instanceof HTMLInputElement && field.type === "checkbox") {
        return String(field.checked);
    }
    return field.value;
}

function setBusyButton(button) {
    const busyLabel = button.dataset.busyLabel || "";
    if (!busyLabel) {
        return;
    }
    button.dataset.originalLabel = button.textContent || "";
    button.textContent = busyLabel;
    button.disabled = true;
}

export function initSetupScreen(root) {
    const setupScreen = root.querySelector("[data-setup-screen]");
    if (!setupScreen) {
        return;
    }

    const trackedFields = Array.from(setupScreen.querySelectorAll("[data-setup-track]"));
    const initialValues = new Map(trackedFields.map((field) => [field, fieldValue(field)]));
    const hasUnsavedChanges = () =>
        trackedFields.some((field) => fieldValue(field) !== initialValues.get(field));

    const secretInputs = setupScreen.querySelectorAll("[data-secret-input]");
    secretInputs.forEach((input) => {
        input.addEventListener("blur", () => {
            input.value = input.value.trim();
        });
    });

    const toggleButtons = setupScreen.querySelectorAll("[data-toggle-target]");
    toggleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const targetSelector = button.dataset.toggleTarget || "";
            const input = setupScreen.querySelector(targetSelector);
            if (!(input instanceof HTMLInputElement)) {
                return;
            }

            const willReveal = input.type === "password";
            input.type = willReveal ? "text" : "password";
            button.textContent = willReveal ? "Hide" : "Show";
            button.setAttribute("aria-pressed", willReveal ? "true" : "false");
        });
    });

    const forms = setupScreen.querySelectorAll("form");
    forms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const submitter = event.submitter;
            if (!(submitter instanceof HTMLButtonElement)) {
                return;
            }

            const trimInputs = form.querySelectorAll("[data-secret-input]");
            trimInputs.forEach((input) => {
                input.value = input.value.trim();
            });

            if (submitter.hasAttribute("data-setup-back") && hasUnsavedChanges()) {
                if (!window.confirm("Discard unsaved setup changes and go back?")) {
                    event.preventDefault();
                    return;
                }
            }

            setBusyButton(submitter);
            const siblingButtons = form.querySelectorAll("button");
            siblingButtons.forEach((button) => {
                if (button !== submitter) {
                    button.disabled = true;
                }
            });
        });
    });
}
