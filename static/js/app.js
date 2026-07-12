import { initLiveClock } from "./clock.js";
import { initHealthPolling } from "./health.js";
import { initLivePreview } from "./camera.js";
import { initUiStatePolling } from "./processing.js";

function initDeleteAllConfirmation(root) {
    const deleteForms = root.querySelectorAll(".delete-all-form");
    if (!deleteForms.length) {
        return;
    }

    deleteForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const stageField = form.querySelector('input[name="confirm_stage"]');
            if (stageField) {
                stageField.value = "";
            }

            if (!window.confirm("Delete all local answers, retry data, and temporary images?")) {
                event.preventDefault();
                return;
            }
            if (!window.confirm("This cannot be undone. Delete all local data now?")) {
                event.preventDefault();
                return;
            }

            if (stageField) {
                stageField.value = "final";
            }
        });
    });
}

const root = document.body;
if (root) {
    initDeleteAllConfirmation(root);
    initUiStatePolling(root);
    initHealthPolling(root);
    initLivePreview(root);
    initLiveClock(root);
}
