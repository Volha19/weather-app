(function () {
    const board = document.getElementById("widget-board");
    const storageKey = "weather-board-order";
    const weatherCharts = {};

    function parseJsonData(value) {
        if (!value) {
            return [];
        }
        // Check that special characters are properly unescaped before parsing
        const normalized = value
            .replace(/&quot;/g, '"')
            .replace(/&#x27;/g, "'")
            .replace(/&amp;/g, "&");

        try {
            return JSON.parse(normalized);
        } catch (error) {
            return [];
        }
    }

    function formatDateLabel(rawDate) {
        const date = new Date(rawDate + "T00:00:00");
        if (Number.isNaN(date.getTime())) {
            return rawDate;
        }

        return date.toLocaleDateString(undefined, {
            weekday: "short",
            month: "short",
            day: "numeric"
        });
    }

    function initForecastCharts() {
        if (typeof Chart === "undefined") {
            return;
        }

        const graphBlocks = document.querySelectorAll(".graph-data");
        graphBlocks.forEach(function (graphDataElement) {
            const canvas = graphDataElement.querySelector("canvas.weather-chart");
            if (!canvas) {
                return;
            }

            const labels = parseJsonData(graphDataElement.dataset.labels);
            const formattedLabels = labels.map(formatDateLabel);
            const maxValues = parseJsonData(graphDataElement.dataset.max);
            const minValues = parseJsonData(graphDataElement.dataset.min);
            const metricLabel = graphDataElement.dataset.metricLabel || "Temperature";
            const metricUnit = graphDataElement.dataset.metricUnit || "°C";

            if (!labels.length) {
                return;
            }

            if (weatherCharts[canvas.id]) {
                weatherCharts[canvas.id].destroy();
            }

            weatherCharts[canvas.id] = new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: formattedLabels,
                datasets: [
                    {
                        label: "Daily Max " + metricLabel,
                        data: maxValues,
                        borderColor: "rgb(255, 99, 132)",
                        backgroundColor: "rgba(255, 99, 132, 0.15)",
                        borderWidth: 2,
                        fill: false,
                        tension: 0.35,
                        pointRadius: 5,
                        pointHoverRadius: 7
                    },
                    {
                        label: "Daily Min " + metricLabel,
                        data: minValues,
                        borderColor: "rgb(54, 162, 235)",
                        backgroundColor: "rgba(54, 162, 235, 0.15)",
                        borderWidth: 2,
                        fill: false,
                        tension: 0.35,
                        pointRadius: 5,
                        pointHoverRadius: 7
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: "top"
                    },
                    title: {
                        display: true,
                        text: "5-Day " + metricLabel + " Forecast"
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: metricLabel + " (" + metricUnit + ")"
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: "Date"
                        }
                    }
                }
            }
        });
        });
    }

    function isGraphSwap(event) {
        const target = event && event.detail ? event.detail.target : null;
        if (!target) {
            return false;
        }

        if (target.id && target.id.indexOf("graph-widget-body-") === 0) {
            return true;
        }

        return Boolean(target.querySelector && target.querySelector(".graph-data"));
    }

    document.addEventListener("DOMContentLoaded", initForecastCharts);
    document.body.addEventListener("htmx:afterSwap", function (event) {
        requestAnimationFrame(function () {
            if (isGraphSwap(event)) {
                initForecastCharts();
            }
            saveCurrentOrder();
        });
    });

    document.body.addEventListener("htmx:afterSettle", function (event) {
        if (isGraphSwap(event)) {
            requestAnimationFrame(initForecastCharts);
        }
    });

    if (!board || typeof Sortable === "undefined") {
        return;
    }

    function saveCurrentOrder() {
        if (!board) {
            return;
        }

        const order = Array.from(board.querySelectorAll(".card"))
            .map(function (card) {
                return card.dataset.widgetId;
            })
            .filter(Boolean);

        localStorage.setItem(storageKey, JSON.stringify(order));
    }

    function removeCard(cardElement) {
        if (!cardElement || !board.contains(cardElement)) {
            return;
        }

        const chartCanvas = cardElement.querySelector("canvas.weather-chart");
        if (chartCanvas && weatherCharts[chartCanvas.id]) {
            weatherCharts[chartCanvas.id].destroy();
            delete weatherCharts[chartCanvas.id];
        }

        cardElement.remove();
        saveCurrentOrder();
    }

    document.body.addEventListener("click", function (event) {
        const removeButton = event.target.closest("[data-remove-card]");
        if (!removeButton || !board) {
            return;
        }

        const cardElement = removeButton.closest(".card");
        removeCard(cardElement);
    });

    function applySavedOrder() {
        const raw = localStorage.getItem(storageKey);
        if (!raw) {
            return;
        }

        let order = [];
        try {
            order = JSON.parse(raw);
        } catch (error) {
            return;
        }

        order.forEach(function (widgetId) {
            const card = board.querySelector('[data-widget-id="' + widgetId + '"]');
            if (card) {
                board.appendChild(card);
            }
        });
    }

    applySavedOrder();

    Sortable.create(board, {
        animation: 180,
        handle: ".drag-handle",
        draggable: ".card",
        ghostClass: "drag-ghost",
        chosenClass: "drag-chosen",
        onEnd: function () {
            saveCurrentOrder();
        }
    });
})();
