(function () {
    const board = document.getElementById("widget-board");
    const storageKey = "weather-board-order";
    const weatherCharts = {};
    const weatherMaps = {};
    const chartModes = {};
    const detailWidthThreshold = 720;

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
        let iso = rawDate;

        if (rawDate && rawDate.indexOf(" ") > -1) {
            iso = rawDate.replace(" ", "T");
        } else if (rawDate && rawDate.indexOf(":") > -1) {
            return rawDate;
        } else {
            iso = rawDate + "T00:00:00";
        }

        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) {
            return rawDate;
        }

        if (rawDate && rawDate.indexOf(" ") > -1) {
            return date.toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit"
            });
        }

        return date.toLocaleDateString(undefined, {
            weekday: "short",
            month: "short",
            day: "numeric"
        });
    }

    function formatDateTimeLabel(rawDate) {
        let iso = rawDate;

        if (rawDate && rawDate.indexOf(" ") > -1) {
            iso = rawDate.replace(" ", "T");
        }

        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) {
            return rawDate;
        }

        return date.toLocaleString(undefined, {
            weekday: "short",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    }

    function getForecastMode(graphDataElement) {
        return graphDataElement.clientWidth >= detailWidthThreshold ? "detail" : "daily";
    }

    function getForecastSeries(graphDataElement, mode) {
        if (mode === "detail") {
            return {
                labels: parseJsonData(graphDataElement.dataset.detailLabels),
                maxValues: parseJsonData(graphDataElement.dataset.detailMax),
                minValues: parseJsonData(graphDataElement.dataset.detailMin),
                labelSuffix: "6-Hour"
            };
        }

        return {
            labels: parseJsonData(graphDataElement.dataset.labels),
            maxValues: parseJsonData(graphDataElement.dataset.max),
            minValues: parseJsonData(graphDataElement.dataset.min),
            labelSuffix: "Daily"
        };
    }

    function getChartTitle(metricLabel, mode) {
        return mode === "detail"
            ? "5-Day 6-Hour " + metricLabel + " Forecast"
            : "5-Day Daily " + metricLabel + " Forecast";
    }

    function renderForecastChart(graphDataElement) {
        if (typeof Chart === "undefined") {
            return;
        }

        const canvas = graphDataElement.querySelector("canvas.weather-chart");
        if (!canvas) {
            return;
        }

        const mode = getForecastMode(graphDataElement);
        const series = getForecastSeries(graphDataElement, mode);
        const metricLabel = graphDataElement.dataset.metricLabel || "Temperature";
        const metricUnit = graphDataElement.dataset.metricUnit || "°C";

        if (!series.labels.length) {
            return;
        }

        if (chartModes[canvas.id] === mode && weatherCharts[canvas.id]) {
            return;
        }

        if (weatherCharts[canvas.id]) {
            weatherCharts[canvas.id].destroy();
        }

        const formattedLabels = mode === "detail"
            ? series.labels.map(formatDateTimeLabel)
            : series.labels.map(formatDateLabel);

        weatherCharts[canvas.id] = new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: formattedLabels,
                datasets: [
                    {
                        label: "Daily Max " + metricLabel,
                        data: series.maxValues,
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
                        data: series.minValues,
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
                        text: getChartTitle(metricLabel, mode)
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
                            text: mode === "detail" ? "Date / Time" : "Date"
                        }
                    }
                }
            }
        });

        chartModes[canvas.id] = mode;
    }

    function initForecastCharts() {
        if (typeof Chart === "undefined") {
            return;
        }

        const graphBlocks = document.querySelectorAll(".graph-data");
        graphBlocks.forEach(function (graphDataElement) {
            if (!graphDataElement.__weatherResizeObserver && typeof ResizeObserver !== "undefined") {
                const observer = new ResizeObserver(function () {
                    requestAnimationFrame(function () {
                        renderForecastChart(graphDataElement);
                    });
                });

                observer.observe(graphDataElement);
                graphDataElement.__weatherResizeObserver = observer;
            }

            renderForecastChart(graphDataElement);
        });
    }

    function buildWeatherMapUrl(layerCode, timeOffsetHours) {
        // Use server-side proxy to keep API key secret. Proxy endpoint expects the same z/x/y placeholders.
        // Note: project URL root mounts app under /weather/ so proxy lives at /weather/widgets/
        const base = '/weather/widgets/map-tile/' + encodeURIComponent(layerCode) + '/{z}/{x}/{y}';
        if (!timeOffsetHours) {
            return base;
        }

        const targetTime = new Date(Date.now() + (Number(timeOffsetHours) * 60 * 60 * 1000));
        const unixTime = Math.floor(targetTime.getTime() / 1000);
        return base + '?date=' + unixTime;
    }

    function getWeatherMapLegend(layerCode) {
        const legends = {
            TA2: {
                title: 'Air temperature at 2 m',
                unit: '°C',
                description: 'Blue is colder, red is hotter. Around 30°C and above is shown in the warmest colors.',
                thresholds: [
                    { value: -65, color: '#821692' },
                    { value: -30, color: '#8257db' },
                    { value: -10, color: '#208cec' },
                    { value: 0, color: '#20c4e8' },
                    { value: 10, color: '#23dddd' },
                    { value: 20, color: '#c2ff28' },
                    { value: 25, color: '#ffc228' },
                    { value: 30, color: '#fc8014' }
                ]
            },
            HRD0: {
                title: 'Relative humidity',
                unit: '%',
                description: 'Drier values are shown with warmer tones; wetter values move toward blue/green.',
                thresholds: [
                    { value: 0, color: '#db1200' },
                    { value: 20, color: '#965700' },
                    { value: 40, color: '#ede100' },
                    { value: 60, color: '#8bd600' },
                    { value: 80, color: '#00a808' },
                    { value: 100, color: '#000099' }
                ]
            },
            CL: {
                title: 'Cloudiness',
                unit: '%',
                description: 'The palette moves from clear skies to thicker cloud cover.',
                thresholds: [
                    { value: 0, color: '#ffffff' },
                    { value: 10, color: '#fdfdff' },
                    { value: 30, color: '#f7f7ff' },
                    { value: 60, color: '#e9e9df' },
                    { value: 100, color: '#d2d2d2' }
                ]
            },
            APM: {
                title: 'Pressure on mean sea level',
                unit: 'hPa',
                description: 'Blue shows lower pressure; orange/red shows higher pressure.',
                thresholds: [
                    { value: 94000, color: '#0073ff' },
                    { value: 96000, color: '#00aaff' },
                    { value: 98000, color: '#4bd0d6' },
                    { value: 100000, color: '#8de7c7' },
                    { value: 102000, color: '#f0b800' },
                    { value: 108000, color: '#c60000' }
                ]
            },
            WND: {
                title: 'Wind speed',
                unit: 'm/s',
                description: 'Colors indicate stronger wind as they move toward darker violet/blue tones.',
                thresholds: [
                    { value: 1, color: '#ffffff' },
                    { value: 5, color: '#eececc' },
                    { value: 15, color: '#b364bc' },
                    { value: 25, color: '#3f213bcc' },
                    { value: 50, color: '#744cace6' },
                    { value: 100, color: '#4600afff' },
                    { value: 200, color: '#0d1126' }
                ]
            }
        };

        return legends[layerCode] || legends.TA2;
    }

    function formatLegendValue(value, unit) {
        if (unit === '°C' || unit === 'm/s' || unit === '%') {
            return String(value) + unit;
        }

        if (unit === 'hPa') {
            return String(value) + ' hPa';
        }

        return String(value);
    }

    function buildGradientStops(thresholds) {
        if (!thresholds || !thresholds.length) {
            return 'linear-gradient(90deg, #ccc, #999)';
        }

        const min = thresholds[0].value;
        const max = thresholds[thresholds.length - 1].value;
        const range = max - min || 1;

        const stops = thresholds.map(function (threshold, index) {
            const percent = ((threshold.value - min) / range) * 100;
            const start = Math.max(0, percent - (index === 0 ? 0 : 2));
            const end = Math.min(100, percent + (index === thresholds.length - 1 ? 0 : 2));
            return threshold.color + ' ' + start.toFixed(2) + '%, ' + threshold.color + ' ' + end.toFixed(2) + '%';
        });

        return 'linear-gradient(90deg, ' + stops.join(', ') + ')';
    }

    function renderWeatherMapLegend(legendElement, layerCode) {
        if (!legendElement) {
            return;
        }

        const legend = getWeatherMapLegend(layerCode);
        const thresholds = legend.thresholds || [];
        const minValue = thresholds.length ? thresholds[0].value : 0;
        const maxValue = thresholds.length ? thresholds[thresholds.length - 1].value : 0;
        const gradient = buildGradientStops(thresholds);
        const labelRow = thresholds.map(function (threshold) {
            return '<span>' + formatLegendValue(threshold.value, legend.unit) + '</span>';
        }).join('');

        legendElement.innerHTML = '' +
            '<div class="weather-map-legend-title">' + legend.title + '<span class="weather-map-legend-unit">(' + legend.unit + ')</span></div>' +
            '<div class="weather-map-legend-desc">' + legend.description + '</div>' +
            '<div class="weather-map-legend-scale" style="background:' + gradient + '"></div>' +
            '<div class="weather-map-legend-labels"><span>' + formatLegendValue(minValue, legend.unit) + '</span><span>' + formatLegendValue(maxValue, legend.unit) + '</span></div>' +
            '<div class="weather-map-legend-points">' + labelRow + '</div>';
    }

    function initWeatherMaps() {
        if (typeof L === 'undefined') {
            return;
        }

        const mapBlocks = document.querySelectorAll('[data-weather-map]');
        mapBlocks.forEach(function (mapElement) {
                // API key is no longer expected in the DOM — tiles are proxied via server.

            const instanceId = mapElement.dataset.instanceId || mapElement.id || 'weather-map';
            const mapId = 'weather-map-instance-' + instanceId;
            const layerSelect = mapElement.closest('.card')?.querySelector('[data-weather-map-layer]');
            const timeBar = mapElement.closest('.card')?.querySelector('[data-weather-map-timebar]');
            const legendElement = mapElement.closest('.card')?.querySelector('[data-weather-map-legend]');

            if (weatherMaps[mapId]) {
                return;
            }

            const map = L.map(mapElement, {
                zoomControl: true,
                worldCopyJump: true,
                preferCanvas: true
            }).setView([20, 0], 2);

            const baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 8,
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);

            let weatherLayer = null;
            let currentLayerCode = mapElement.dataset.layer || 'TA2';
            let currentTimeOffset = Number(mapElement.dataset.timeOffset || 0);

            function syncTimeButtons() {
                if (!timeBar) {
                    return;
                }

                timeBar.querySelectorAll('[data-weather-map-time]').forEach(function (button) {
                    button.classList.toggle('is-active', Number(button.dataset.weatherMapTime || 0) === currentTimeOffset);
                });
            }

            function setWeatherLayer(layerCode) {
                if (weatherLayer) {
                    map.removeLayer(weatherLayer);
                }
                weatherLayer = L.tileLayer(buildWeatherMapUrl(layerCode, currentTimeOffset), {
                    opacity: 0.65,
                    attribution: '&copy; OpenWeather'
                }).addTo(map);
                currentLayerCode = layerCode;
                mapElement.dataset.layer = layerCode;
                renderWeatherMapLegend(legendElement, layerCode);
            }

            function setWeatherTimeOffset(timeOffsetHours) {
                currentTimeOffset = Number(timeOffsetHours) || 0;
                mapElement.dataset.timeOffset = String(currentTimeOffset);
                syncTimeButtons();
                setWeatherLayer(currentLayerCode);
            }

            if (layerSelect) {
                layerSelect.value = currentLayerCode;
                layerSelect.addEventListener('change', function () {
                    setWeatherLayer(layerSelect.value);
                });
            }

            if (timeBar) {
                timeBar.addEventListener('click', function (event) {
                    const button = event.target.closest('[data-weather-map-time]');
                    if (!button) {
                        return;
                    }
                    setWeatherTimeOffset(button.dataset.weatherMapTime);
                });
            }

            setWeatherLayer(currentLayerCode);
            syncTimeButtons();

            const observer = new ResizeObserver(function () {
                requestAnimationFrame(function () {
                    map.invalidateSize();
                });
            });

            observer.observe(mapElement);

            weatherMaps[mapId] = {
                map: map,
                baseLayer: baseLayer,
                observer: observer
            };
        });
    }

    function initStatsRefresh() {
        if (!board || typeof window.htmx === 'undefined') {
            return;
        }

        const statsWidgets = board.querySelectorAll('[id^="stats-widget-body-"]');
        statsWidgets.forEach(function (widget) {
            if (widget._statsRefreshTimer) {
                return;
            }

            widget._statsRefreshTimer = window.setInterval(function () {
                const url = widget.getAttribute('hx-get');
                if (!url) {
                    return;
                }

                window.htmx.ajax('GET', url, {
                    target: widget,
                    swap: 'innerHTML'
                });
            }, 60 * 60 * 1000);
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
    document.addEventListener("DOMContentLoaded", initWeatherMaps);
    document.addEventListener("DOMContentLoaded", initStatsRefresh);
    document.body.addEventListener("htmx:afterSwap", function (event) {
        requestAnimationFrame(function () {
            if (isGraphSwap(event)) {
                initForecastCharts();
            }
            initWeatherMaps();
            initStatsRefresh();
            saveCurrentOrder();
        });
    });

    document.body.addEventListener("htmx:afterSettle", function (event) {
        if (isGraphSwap(event)) {
            requestAnimationFrame(initForecastCharts);
        }
        requestAnimationFrame(initWeatherMaps);
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

        const weatherMapElement = cardElement.querySelector('[data-weather-map]');
        if (weatherMapElement) {
            const mapKey = 'weather-map-instance-' + (weatherMapElement.dataset.instanceId || weatherMapElement.id || 'weather-map');
            const weatherMap = weatherMaps[mapKey];
            if (weatherMap) {
                weatherMap.observer.disconnect();
                weatherMap.map.remove();
                delete weatherMaps[mapKey];
            }
        }

        cardElement.remove();
        saveCurrentOrder();
    }

    function toggleCardWidth(cardElement) {
        if (!cardElement) return;
        const isExpanded = cardElement.classList.contains('span-12');
        const nextExpanded = !isExpanded;

        // Remove any old temporary wrapper from previous animation attempts.
        const existingInner = cardElement.querySelector('.card-inner');
        if (existingInner) {
            while (existingInner.firstChild) {
                cardElement.insertBefore(existingInner.firstChild, existingInner);
            }
            existingInner.remove();
        }

        const allCards = Array.from(board.querySelectorAll('.card'));
        const oldRects = new Map();
        allCards.forEach(function (card) {
            oldRects.set(card, card.getBoundingClientRect());
        });

        if (nextExpanded) {
            cardElement.classList.remove('span-6');
            cardElement.classList.add('span-12');
        } else {
            cardElement.classList.remove('span-12');
            cardElement.classList.add('span-6');
        }

        const toggleBtn = cardElement.querySelector('[data-toggle-width]');
        if (toggleBtn) {
            toggleBtn.innerHTML = nextExpanded
                ? '<i class="bi bi-arrows-collapse-vertical"></i>'
                : '<i class="bi bi-arrows-expand-vertical"></i>';
            toggleBtn.classList.toggle('expanded', nextExpanded);
            toggleBtn.setAttribute('aria-label', nextExpanded ? 'Collapse card' : 'Expand card');
            toggleBtn.setAttribute('title', nextExpanded ? 'Collapse card' : 'Expand card');
        }

        cardElement.style.transition = 'opacity 180ms ease, box-shadow 180ms ease';
        cardElement.style.opacity = '0.985';
        requestAnimationFrame(function () {
            cardElement.style.opacity = '';
        });

        requestAnimationFrame(function () {
            const newRects = new Map();
            allCards.forEach(function (card) {
                newRects.set(card, card.getBoundingClientRect());
            });

            allCards.forEach(function (card) {
                if (card === cardElement) return;
                const oldRect = oldRects.get(card);
                const newRect = newRects.get(card);
                if (!oldRect || !newRect) return;

                const dx = oldRect.left - newRect.left;
                const dy = oldRect.top - newRect.top;
                if (dx === 0 && dy === 0) return;

                card.style.transition = 'none';
                card.style.transform = `translate(${dx}px, ${dy}px)`;
                card.style.willChange = 'transform';
                card.getBoundingClientRect();

                requestAnimationFrame(function () {
                    card.style.transition = 'transform 260ms cubic-bezier(.2,.8,.2,1)';
                    card.style.transform = '';
                });

                function cleanup(ev) {
                    if (ev && ev.propertyName && ev.propertyName !== 'transform') return;
                    card.removeEventListener('transitionend', cleanup);
                    card.style.transition = '';
                    card.style.transform = '';
                    card.style.willChange = '';
                }

                card.addEventListener('transitionend', cleanup);
            });
        });

        setTimeout(function () {
            cardElement.style.transition = '';
            cardElement.style.opacity = '';
            cardElement.style.boxShadow = '';
        }, 220);

        const graph = cardElement.querySelector('.graph-data');
        if (graph) {
            renderForecastChart(graph);
        }
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

    document.body.addEventListener('click', function (event) {
        const toggle = event.target.closest('[data-toggle-width]');
        if (!toggle) return;
        const cardElement = toggle.closest('.card');
        toggleCardWidth(cardElement);
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
