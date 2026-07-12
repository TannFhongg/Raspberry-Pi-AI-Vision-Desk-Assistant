export function initLiveClock(root) {
    const clockElement = root.querySelector("[data-live-clock]");
    if (!clockElement) {
        return;
    }

    const timeElement = clockElement.querySelector("[data-live-clock-time]");
    const dayElement = clockElement.querySelector("[data-live-clock-day]");
    if (!timeElement || !dayElement) {
        return;
    }

    const locale = clockElement.dataset.locale || "en";
    const updateClock = () => {
        const now = new Date();
        const hours = now.getHours();
        const minutes = String(now.getMinutes()).padStart(2, "0");
        const meridiem = hours >= 12 ? "P.M" : "A.M";
        let displayHours = hours % 12;
        if (displayHours === 0) {
            displayHours = 12;
        }

        timeElement.textContent = `${displayHours}:${minutes} ${meridiem}`;
        dayElement.textContent = now.toLocaleDateString(locale, {
            weekday: "long",
        });
    };

    updateClock();
    window.setInterval(updateClock, 1000);
}
