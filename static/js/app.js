(() => {
    "use strict";

    const searchForm = document.getElementById("weather-search");
    const cityInput = document.getElementById("city-input");
    const countryInput = document.getElementById("country-input");
    const searchButton = document.getElementById("search-button");
    const forecastList = document.getElementById("forecast-list");
    const favoritesList = document.getElementById("favorites-list");
    const favoriteModalElement = document.getElementById("favorite-modal");
    const favoriteForm = document.getElementById("favorite-form");
    const favoriteSubmit = document.getElementById("favorite-submit");
    const notifications = document.getElementById("notifications");
    const favoriteModal = window.bootstrap
        ? window.bootstrap.Modal.getOrCreateInstance(favoriteModalElement)
        : null;
    let activeWeatherRequest = 0;
    let lastSearchedCity = "";
    let lastSearchedCountry = "";
    let favoriteMutationInProgress = false;
    let showingAllFavorites = false;
    const WEATHER_CACHE_DURATION = 60 * 1000;
    const weatherCache = new Map();
    const WORLD_CITIES = [
        { name: "New York", country: "US", image: "reference-new-york.png" },
        { name: "London", country: "GB", image: "reference-london.png" },
        { name: "Tokyo", country: "JP", image: "reference-tokyo.png" },
        { name: "Sydney", country: "AU", image: "reference-sydney.png" },
    ];

    async function requestJson(url, options = {}) {
        let response;
        try {
            response = await fetch(url, options);
        } catch (_error) {
            throw new Error("Unable to reach WeatherHub. Check your connection and try again.");
        }

        let payload;
        try {
            payload = await response.json();
        } catch (_error) {
            throw new Error("The server returned an unreadable response. Please try again.");
        }

        if (!response.ok || payload?.success !== true) {
            throw new Error(payload?.error?.message || `Request failed (${response.status}).`);
        }
        if (!payload.data || typeof payload.data !== "object") {
            throw new Error("The server returned an incomplete response. Please try again.");
        }
        return payload.data;
    }

    function currentWeatherFor(city, country) {
        const key = `${city.trim().toLocaleLowerCase()}|${country.trim().toUpperCase()}`;
        const cached = weatherCache.get(key);
        if (cached && cached.expiresAt > Date.now()) return cached.promise;

        const query = new URLSearchParams({ city, country });
        const entry = {
            expiresAt: Date.now() + WEATHER_CACHE_DURATION,
            promise: requestJson(`/api/weather/current?${query.toString()}`),
        };
        weatherCache.set(key, entry);
        entry.promise.catch(() => {
            if (weatherCache.get(key) === entry) weatherCache.delete(key);
        });
        return entry.promise;
    }

    function showNotification(message, kind = "danger") {
        notifications.replaceChildren();
        const alert = document.createElement("div");
        alert.className = `alert alert-${kind === "success" ? "success" : "danger"} alert-dismissible fade show`;
        alert.setAttribute("role", kind === "success" ? "status" : "alert");
        alert.append(document.createTextNode(message));
        const close = document.createElement("button");
        close.type = "button";
        close.className = "btn-close";
        close.setAttribute("data-bs-dismiss", "alert");
        close.setAttribute("aria-label", "Dismiss");
        alert.append(close);
        notifications.append(alert);
    }

    function setButtonLoading(button, loading, label) {
        const labelElement = button.querySelector(".button-label");
        const spinner = button.querySelector(".spinner-border");
        button.disabled = loading;
        if (labelElement) labelElement.textContent = loading ? "Loading…" : label;
        spinner?.classList.toggle("d-none", !loading);
    }

    function numberOrNull(value) {
        return typeof value === "number" && Number.isFinite(value) ? value : null;
    }

    function formatNumber(value, digits = 0) {
        const number = numberOrNull(value);
        return number === null ? "—" : number.toFixed(digits);
    }

    function iconUrl(code) {
        return typeof code === "string" && /^\d{2}[dn]$/.test(code)
            ? `https://openweathermap.org/img/wn/${code}@2x.png`
            : "";
    }

    function setWeatherIcon(image, code) {
        const url = iconUrl(code);
        image.classList.toggle("d-none", !url);
        if (url) {
            const existingErrorHandler = image.onerror;
            image.onerror = () => {
                image.classList.add("d-none");
                image.removeAttribute("src");
                if (typeof existingErrorHandler === "function") {
                    existingErrorHandler.call(image);
                }
            };
            image.src = url;
        } else {
            image.removeAttribute("src");
        }
    }

    function localDate(timestamp, timezone = 0, options = { weekday: "long", day: "numeric", month: "long", year: "numeric" }) {
        if (typeof timestamp !== "number" || !Number.isFinite(timestamp)) return "";
        const date = new Date((timestamp + timezone) * 1000);
        return new Intl.DateTimeFormat(undefined, { ...options, timeZone: "UTC" }).format(date);
    }

    function clearCurrentWeather(description) {
        document.getElementById("current-city").textContent = "—";
        document.getElementById("current-country").textContent = "";
        document.getElementById("current-location").textContent = "Location unavailable";
        document.getElementById("current-description").textContent = description;
        for (const id of ["current-temp", "feels-like", "feels-like-card", "humidity", "wind-speed", "pressure", "visibility"]) {
            document.getElementById(id).textContent = "—";
        }
        document.getElementById("current-date").textContent = "Search for a city to see local weather";
        document.getElementById("current-time").textContent = "";
        document.getElementById("header-date").textContent = "Local weather";
        document.getElementById("header-time").textContent = "—";
        setWeatherIcon(document.getElementById("current-icon"), null);
    }

    function renderCurrentWeather(data) {
        const description = data.weather?.[0]?.description;
        const location = data.location || data;
        const city = location.city || data.name;
        document.getElementById("current-city").textContent = city || "Weather";
        const countryCode = typeof location.country === "string"
            ? location.country
            : typeof data.sys?.country === "string" ? data.sys.country : "";
        document.getElementById("current-country").textContent = countryCode;
        const countryName = countryCode && typeof Intl.DisplayNames === "function"
            ? new Intl.DisplayNames(undefined, { type: "region" }).of(countryCode)
            : countryCode;
        const state = location.state || location.region;
        document.getElementById("current-location").textContent =
            [state, countryName].filter(Boolean).join(", ") || "Location unavailable";
        document.getElementById("current-description").textContent =
            typeof description === "string" ? description : "Conditions unavailable";
        document.getElementById("current-temp").textContent = formatNumber(data.main?.temp, 1);
        const feelsLike = numberOrNull(data.main?.feels_like) === null
            ? "—"
            : `${formatNumber(data.main.feels_like, 1)}°C`;
        document.getElementById("feels-like").textContent = feelsLike;
        document.getElementById("feels-like-card").textContent = feelsLike;
        document.getElementById("humidity").textContent =
            numberOrNull(data.main?.humidity) === null ? "—" : `${formatNumber(data.main.humidity)}%`;
        document.getElementById("wind-speed").textContent =
            numberOrNull(data.wind?.speed) === null ? "—" : `${formatNumber(data.wind.speed, 1)} m/s`;
        document.getElementById("pressure").textContent =
            numberOrNull(data.main?.pressure) === null ? "—" : `${formatNumber(data.main.pressure)} hPa`;
        document.getElementById("visibility").textContent =
            numberOrNull(data.visibility) === null ? "—" : `${formatNumber(data.visibility / 1000, 1)} km`;
        document.getElementById("current-date").textContent =
            localDate(data.dt, numberOrNull(data.timezone) ?? 0) || "Local date unavailable";
        const localWeatherDate = numberOrNull(data.dt) === null
            ? null
            : new Date((data.dt + (numberOrNull(data.timezone) ?? 0)) * 1000);
        document.getElementById("current-time").textContent = localWeatherDate
            ? new Intl.DateTimeFormat(undefined, {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
                timeZone: "UTC",
            }).format(localWeatherDate)
            : "";
        document.getElementById("header-date").textContent =
            localDate(data.dt, numberOrNull(data.timezone) ?? 0, { weekday: "short", day: "numeric", month: "short", year: "numeric" }) || "Local weather";
        document.getElementById("header-time").textContent =
            document.getElementById("current-time").textContent || "—";
        setWeatherIcon(document.getElementById("current-icon"), data.weather?.[0]?.icon);
    }

    function renderForecast(data) {
        const entries = Array.isArray(data.list) ? data.list : [];
        const timezone = numberOrNull(data.city?.timezone) ?? 0;
        const grouped = new Map();
        for (const entry of entries) {
            if (typeof entry?.dt !== "number" || !Number.isFinite(entry.dt)) continue;
            const date = new Date((entry.dt + timezone) * 1000);
            const key = `${date.getUTCFullYear()}-${date.getUTCMonth()}-${date.getUTCDate()}`;
            if (!grouped.has(key)) grouped.set(key, []);
            grouped.get(key).push(entry);
        }

        const days = [...grouped.values()].slice(0, 5);
        forecastList.replaceChildren();
        if (!days.length) {
            const empty = document.createElement("div");
            empty.className = "forecast-placeholder";
            empty.textContent = "No forecast entries are available for this city.";
            forecastList.append(empty);
            return;
        }

        for (const [index, dayEntries] of days.entries()) {
            const temperatures = dayEntries
                .map((entry) => numberOrNull(entry.main?.temp))
                .filter((temperature) => temperature !== null);
            const low = temperatures.length ? Math.min(...temperatures) : null;
            const high = temperatures.length ? Math.max(...temperatures) : null;
            const representative = dayEntries.reduce((best, entry) => {
                const hour = new Date((entry.dt + timezone) * 1000).getUTCHours();
                const bestHour = new Date((best.dt + timezone) * 1000).getUTCHours();
                return Math.abs(hour - 12) < Math.abs(bestHour - 12) ? entry : best;
            }, dayEntries[0]);
            const descriptions = representative.weather?.[0]?.description;
            const precipitation = dayEntries
                .map((entry) => numberOrNull(entry.pop))
                .filter((probability) => probability !== null);
            const probability = precipitation.length ? Math.round(Math.max(...precipitation) * 100) : null;

            const card = document.createElement("article");
            card.className = "forecast-card";
            const day = document.createElement("span");
            day.className = "forecast-day";
            day.textContent = localDate(representative.dt, timezone, { weekday: "short" });
            const date = document.createElement("span");
            date.className = "forecast-date";
            date.textContent = localDate(representative.dt, timezone, { day: "numeric", month: "short" });
            const icon = document.createElement("img");
            icon.className = "forecast-icon";
            icon.alt = typeof descriptions === "string" ? descriptions : "Weather conditions";
            setWeatherIcon(icon, representative.weather?.[0]?.icon);

            const temps = document.createElement("div");
            temps.className = "forecast-temps";
            const highSpan = document.createElement("span");
            highSpan.className = "temp-high";
            highSpan.textContent = high === null ? "—°" : `${Math.round(high)}°`;
            const sepSpan = document.createElement("span");
            sepSpan.className = "temp-sep";
            sepSpan.textContent = " / ";
            const lowSpan = document.createElement("span");
            lowSpan.className = "temp-low";
            lowSpan.textContent = low === null ? "—°" : `${Math.round(low)}°`;
            temps.append(highSpan, sepSpan, lowSpan);

            const description = document.createElement("span");
            description.className = "forecast-desc";
            description.textContent = typeof descriptions === "string" ? descriptions : "Conditions unavailable";

            card.append(day, date);
            if (!icon.classList.contains("d-none")) card.append(icon);
            card.append(temps, description);
            if (probability !== null) {
                const pop = document.createElement("div");
                pop.className = "forecast-pop";
                const drop = document.createElement("i");
                drop.className = "bi bi-droplet-fill";
                drop.setAttribute("aria-hidden", "true");
                pop.append(drop, document.createTextNode(` ${probability}%`));
                card.append(pop);
            }
            forecastList.append(card);
        }
    }

    async function loadWeather(city, country, silent = false) {
        lastSearchedCity = city;
        lastSearchedCountry = country;
        const requestId = ++activeWeatherRequest;
        const query = new URLSearchParams({ city, country });
        if (!silent) {
            setButtonLoading(searchButton, true, "Search");
            notifications.replaceChildren();
            clearCurrentWeather("Loading current conditions…");
            forecastList.replaceChildren();
            const placeholder = document.createElement("div");
            placeholder.className = "forecast-placeholder";
            placeholder.textContent = "Loading forecast…";
            forecastList.append(placeholder);
        }

        try {
            let current;
            try {
                current = await requestJson(`/api/weather/current?${query.toString()}`);
            } catch (error) {
                if (requestId !== activeWeatherRequest) return;
                if (!silent) {
                    clearCurrentWeather("Weather unavailable");
                    forecastList.replaceChildren();
                    const unavailable = document.createElement("div");
                    unavailable.className = "forecast-placeholder";
                    unavailable.textContent = "Search for a valid city to see its forecast.";
                    forecastList.append(unavailable);
                }
                showNotification(error.message);
                return;
            }
            if (requestId !== activeWeatherRequest) return;
            renderCurrentWeather(current);

            const location = current.location || current;
            const forecastQuery = new URLSearchParams({
                city: location.city || city,
                country: location.country || country,
            });
            if (location.state) forecastQuery.set("state", location.state);
            if (numberOrNull(location.latitude) !== null) {
                forecastQuery.set("latitude", String(location.latitude));
            }
            if (numberOrNull(location.longitude) !== null) {
                forecastQuery.set("longitude", String(location.longitude));
            }

            let forecast;
            try {
                forecast = await requestJson(
                    `/api/weather/forecast?${forecastQuery.toString()}`
                );
            } catch (error) {
                if (requestId !== activeWeatherRequest) return;
                if (!silent) {
                    forecastList.replaceChildren();
                    const unavailable = document.createElement("div");
                    unavailable.className = "forecast-placeholder";
                    unavailable.textContent = error.message;
                    forecastList.append(unavailable);
                }
                showNotification(error.message);
                return;
            }
            if (requestId !== activeWeatherRequest) return;
            renderForecast(forecast);
        } finally {
            if (!silent && requestId === activeWeatherRequest) {
                setButtonLoading(searchButton, false, "Search");
            }
        }
    }

    function addFavoriteAction(button, icon, label, action, id) {
        button.type = "button";
        button.className = `favorite-${action}`;
        button.setAttribute("aria-label", `${label} favorite`);
        button.title = `${label} favorite`;
        button.dataset.favoriteId = String(id);
        const glyph = document.createElement("i");
        glyph.className = `bi ${icon}`;
        glyph.setAttribute("aria-hidden", "true");
        button.append(glyph);
    }

    function mapUrlFor(weather) {
        const latitude = numberOrNull(weather.coord?.lat);
        const longitude = numberOrNull(weather.coord?.lon);
        if (latitude === null || longitude === null) return "";
        return `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=10/${latitude}/${longitude}`;
    }

    function weatherIconElements(code) {
        const wrapper = document.createElement("span");
        wrapper.className = "world-city-weather";
        const icon = document.createElement("img");
        icon.alt = "";
        icon.classList.add("d-none");
        icon.onerror = () => {
            icon.classList.add("d-none");
            icon.removeAttribute("src");
        };
        wrapper.append(icon);
        if (iconUrl(code)) {
            setWeatherIcon(icon, code);
        }
        return wrapper;
    }

    function renderWorldCity(city, weather) {
        const row = document.createElement("article");
        row.className = "world-city-row";
        const photo = document.createElement("img");
        photo.className = "world-city-photo";
        photo.src = `/static/images/${encodeURIComponent(city.image)}`;
        photo.alt = `${city.name} city view`;
        photo.loading = "lazy";
        photo.onerror = () => photo.classList.add("d-none");

        const name = document.createElement("div");
        name.className = "world-city-name";
        name.textContent = `${city.name}, ${city.country}`;
        const description = typeof weather?.weather?.[0]?.description === "string"
            ? weather.weather[0].description
            : "Weather unavailable";
        const conditions = weatherIconElements(weather?.weather?.[0]?.icon);
        const info = document.createElement("div");
        info.className = "world-city-info";
        const temperature = document.createElement("div");
        temperature.className = "world-city-temperature";
        temperature.textContent = numberOrNull(weather?.main?.temp) === null
            ? "—"
            : `${formatNumber(weather.main.temp, 1)}°C`;
        const condition = document.createElement("div");
        condition.className = "world-city-description";
        condition.textContent = description;
        info.append(temperature, condition);

        row.append(photo, name, conditions, info);
        const mapUrl = weather ? mapUrlFor(weather) : "";
        if (mapUrl) {
            const mapLink = document.createElement("a");
            mapLink.className = "world-city-link";
            mapLink.href = mapUrl;
            mapLink.target = "_blank";
            mapLink.rel = "noopener noreferrer";
            mapLink.setAttribute("aria-label", `View ${city.name} on OpenStreetMap`);
            mapLink.title = "View on OpenStreetMap";
            mapLink.textContent = "›";
            row.append(mapLink);
        }
        return { row, mapUrl };
    }

    async function loadWorldWeather(silent = false) {
        const worldList = document.getElementById("world-city-list");
        const worldMapLink = document.getElementById("world-map-link");
        if (!silent) {
            worldList.replaceChildren();
            const loading = document.createElement("p");
            loading.className = "world-loading";
            loading.textContent = "Loading world weather…";
            worldList.append(loading);
        }

        let results;
        try {
            results = await Promise.allSettled(
                WORLD_CITIES.map((city) => currentWeatherFor(city.name, city.country)),
            );
        } catch (error) {
            if (!silent) {
                worldList.replaceChildren();
                const failed = document.createElement("p");
                failed.className = "world-unavailable";
                failed.textContent = "World weather unavailable.";
                worldList.append(failed);
            }
            showNotification("Failed to refresh world weather.");
            return;
        }

        const fragment = document.createDocumentFragment();
        let firstMapUrl = "";
        results.forEach((result, index) => {
            const weather = result.status === "fulfilled" ? result.value : null;
            const rendered = renderWorldCity(WORLD_CITIES[index], weather);
            fragment.append(rendered.row);
            if (!firstMapUrl && rendered.mapUrl) firstMapUrl = rendered.mapUrl;
        });
        worldList.replaceChildren(fragment);
        if (firstMapUrl) {
            worldMapLink.href = firstMapUrl;
            worldMapLink.hidden = false;
        } else {
            worldMapLink.hidden = true;
            worldMapLink.removeAttribute("href");
        }
    }

    let savedFavorites = [];

    function updateFavoriteWeather(card) {
        const { city = "", country = "" } = card.dataset;
        const temperature = card.querySelector(".favorite-temperature");
        const description = card.querySelector(".favorite-description");
        const symbol = card.querySelector(".favorite-symbol");
        const weatherIcon = symbol.querySelector("img");

        currentWeatherFor(city, country)
            .then((weather) => {
                temperature.textContent = numberOrNull(weather.main?.temp) === null
                    ? "—"
                    : `${formatNumber(weather.main.temp, 1)}°C`;
                description.textContent = typeof weather.weather?.[0]?.description === "string"
                    ? weather.weather[0].description
                    : "Conditions unavailable";
                const code = weather.weather?.[0]?.icon;
                if (iconUrl(code)) {
                    setWeatherIcon(weatherIcon, code);
                } else {
                    weatherIcon.classList.add("d-none");
                    weatherIcon.removeAttribute("src");
                }
            })
            .catch(() => {
                description.textContent = "Weather unavailable";
                weatherIcon.classList.add("d-none");
                weatherIcon.removeAttribute("src");
            });
    }

    function renderFavoriteRows() {
        favoritesList.replaceChildren();
        const visibleFavorites = showingAllFavorites
            ? savedFavorites
            : savedFavorites.slice(0, 5);

        if (!visibleFavorites.length) {
            const empty = document.createElement("div");
            empty.className = "favorites-placeholder";
            empty.textContent = "No favorite cities yet. Add one to keep it close.";
            favoritesList.append(empty);
        }

        for (const favorite of visibleFavorites) {
            const card = document.createElement("article");
            card.className = "favorite-card";
            card.dataset.city = favorite.city || "";
            card.dataset.country = favorite.country || "";
            const symbol = document.createElement("button");
            symbol.type = "button";
            symbol.className = "favorite-symbol";
            symbol.setAttribute("aria-label", `View weather for ${favorite.city || "favorite city"}`);
            symbol.title = "View weather";
            symbol.addEventListener("click", () => {
                cityInput.value = favorite.city || "";
                countryInput.value = favorite.country || "";
                document.getElementById("overview").scrollIntoView({ behavior: "smooth" });
                searchForm.requestSubmit();
            });
            const weatherIcon = document.createElement("img");
            weatherIcon.classList.add("d-none");
            weatherIcon.alt = "";
            weatherIcon.onerror = () => {
                weatherIcon.classList.add("d-none");
                weatherIcon.removeAttribute("src");
            };
            symbol.append(weatherIcon);

            const details = document.createElement("div");
            details.className = "favorite-details";
            const name = document.createElement("div");
            name.className = "favorite-name";
            name.textContent = favorite.city || "Favorite city";
            const meta = document.createElement("div");
            meta.className = "favorite-meta";
            meta.textContent = [favorite.country, favorite.nickname].filter(Boolean).join(" | ");
            details.append(name, meta);

            const weatherSummary = document.createElement("div");
            weatherSummary.className = "favorite-weather";
            const temperature = document.createElement("span");
            temperature.className = "favorite-temperature";
            temperature.textContent = "—";
            const description = document.createElement("span");
            description.className = "favorite-description";
            description.textContent = "Loading";
            weatherSummary.append(temperature, description);

            const actions = document.createElement("div");
            actions.className = "favorite-actions";
            const edit = document.createElement("button");
            addFavoriteAction(edit, "bi-pencil", "Edit", "edit", favorite.id);
            edit.addEventListener("click", () => editFavorite(favorite.id));
            const remove = document.createElement("button");
            addFavoriteAction(remove, "bi-trash3", "Delete", "delete", favorite.id);
            remove.addEventListener("click", () => deleteFavorite(favorite.id, favorite.city, remove));
            actions.append(edit, remove);
            card.append(symbol, details, weatherSummary, actions);
            favoritesList.append(card);
            updateFavoriteWeather(card);
        }

        const viewAllButton = document.getElementById("view-all-favorites");
        viewAllButton.hidden = savedFavorites.length === 0;
        viewAllButton.setAttribute("aria-expanded", String(showingAllFavorites));
        viewAllButton.replaceChildren();
        viewAllButton.append(
            document.createTextNode(showingAllFavorites ? "Show Fewer Favourite Cities " : "View All Favourite Cities "),
        );
        const arrow = document.createElement("i");
        arrow.className = `bi ${showingAllFavorites ? "bi-arrow-up" : "bi-arrow-right"}`;
        arrow.setAttribute("aria-hidden", "true");
        viewAllButton.append(arrow);
    }

    async function loadFavorites() {
        favoritesList.replaceChildren();
        const loading = document.createElement("div");
        loading.className = "favorites-placeholder";
        loading.textContent = "Loading your favorite cities…";
        favoritesList.append(loading);
        try {
            const data = await requestJson("/api/favorites");
            if (!Array.isArray(data.favorites)) {
                throw new Error("The favorites response was incomplete. Please refresh and try again.");
            }
            savedFavorites = data.favorites;
            renderFavoriteRows();
        } catch (error) {
            favoritesList.replaceChildren();
            const failed = document.createElement("div");
            failed.className = "favorites-placeholder";
            failed.textContent = error.message;
            favoritesList.append(failed);
        }
    }

    function resetFavoriteForm() {
        favoriteForm.reset();
        document.getElementById("favorite-id").value = "";
        document.getElementById("favorite-modal-title").textContent = "Add a favorite city";
        setButtonLoading(favoriteSubmit, false, "Save city");
    }

    async function editFavorite(id) {
        try {
            const data = await requestJson(`/api/favorites/${encodeURIComponent(id)}`);
            const favorite = data.favorite;
            document.getElementById("favorite-id").value = favorite.id;
            document.getElementById("favorite-city").value = favorite.city || "";
            document.getElementById("favorite-country").value = favorite.country || "";
            document.getElementById("favorite-nickname").value = favorite.nickname || "";
            document.getElementById("favorite-modal-title").textContent = "Edit favorite city";
            favoriteModal?.show();
        } catch (error) {
            showNotification(error.message);
        }
    }

    async function deleteFavorite(id, city, button) {
        if (favoriteMutationInProgress) return;
        if (!window.confirm(`Remove ${city || "this city"} from your favorites?`)) return;
        favoriteMutationInProgress = true;
        button.disabled = true;
        try {
            await requestJson(`/api/favorites/${encodeURIComponent(id)}`, { method: "DELETE" });
            showNotification("Favorite city removed.", "success");
            await loadFavorites();
        } catch (error) {
            showNotification(error.message);
        } finally {
            favoriteMutationInProgress = false;
            button.disabled = false;
        }
    }

    searchForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const city = cityInput.value.trim();
        const country = countryInput.value.trim().toUpperCase();
        if (!city) {
            cityInput.focus();
            showNotification("Enter a city name to search.");
            return;
        }
        if (country && !/^[A-Z]{2}$/.test(country)) {
            countryInput.focus();
            showNotification("Country code must contain two letters, such as IN or US.");
            return;
        }
        countryInput.value = country;
        loadWeather(city, country);
    });

    favoriteForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (favoriteMutationInProgress) return;
        if (!favoriteForm.reportValidity()) return;
        const city = document.getElementById("favorite-city").value.trim();
        const country = document.getElementById("favorite-country").value.trim().toUpperCase();
        const nickname = document.getElementById("favorite-nickname").value.trim();
        if (!city) {
            document.getElementById("favorite-city").focus();
            return;
        }
        if (!/^[A-Z]{2}$/.test(country)) {
            showNotification("Country code must contain two letters, such as IN or US.");
            document.getElementById("favorite-country").focus();
            return;
        }
        const id = document.getElementById("favorite-id").value;
        favoriteMutationInProgress = true;
        setButtonLoading(favoriteSubmit, true, id ? "Update city" : "Save city");
        try {
            await requestJson(
                id ? `/api/favorites/${encodeURIComponent(id)}` : "/api/favorites",
                {
                    method: id ? "PUT" : "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ city, country, nickname: nickname || null }),
                },
            );
            favoriteModal?.hide();
            resetFavoriteForm();
            showNotification(id ? "Favorite city updated." : "Favorite city added.", "success");
            await loadFavorites();
        } catch (error) {
            showNotification(error.message);
        } finally {
            favoriteMutationInProgress = false;
            setButtonLoading(favoriteSubmit, false, id ? "Update city" : "Save city");
        }
    });

    favoriteModalElement.addEventListener("show.bs.modal", (event) => {
        if (event.relatedTarget?.id === "add-favorite-button") resetFavoriteForm();
    });

    document.getElementById("theme-toggle").addEventListener("click", (event) => {
        const enabled = document.body.classList.toggle("light-theme");
        document.documentElement.dataset.bsTheme = enabled ? "light" : "dark";
        try {
            window.localStorage.setItem("weatherhub-theme", enabled ? "light" : "dark");
        } catch (_error) {
            showNotification("Theme preference could not be saved in this browser.", "danger");
        }
        const button = event.currentTarget;
        button.setAttribute("aria-label", enabled ? "Switch to dark mode" : "Switch to light mode");
        button.dataset.mode = enabled ? "light" : "dark";
    });

    try {
        if (window.localStorage.getItem("weatherhub-theme") === "light") {
            document.body.classList.add("light-theme");
            document.documentElement.dataset.bsTheme = "light";
            const toggle = document.getElementById("theme-toggle");
            toggle.setAttribute("aria-label", "Switch to dark mode");
            toggle.dataset.mode = "light";
        }
    } catch (_error) {
        // The dashboard remains usable when browser storage is unavailable.
    }

    document.getElementById("add-favorite-button").addEventListener("click", () => {
        document.getElementById("favorite-modal-title").textContent = "Add a favorite city";
    });

    document.getElementById("view-all-favorites").addEventListener("click", () => {
        showingAllFavorites = !showingAllFavorites;
        renderFavoriteRows();
    });

    const sidebar = document.querySelector(".sidebar");
    const mobileNavToggle = document.getElementById("mobile-nav-toggle");
    mobileNavToggle.addEventListener("click", () => {
        const expanded = mobileNavToggle.getAttribute("aria-expanded") !== "true";
        mobileNavToggle.setAttribute("aria-expanded", String(expanded));
        mobileNavToggle.setAttribute("aria-label", expanded ? "Close navigation" : "Open navigation");
        mobileNavToggle.querySelector("i").className = `bi ${expanded ? "bi-x-lg" : "bi-list"}`;
        sidebar.classList.toggle("is-open", expanded);
    });
    document.querySelectorAll(".side-link").forEach((link) => {
        link.addEventListener("click", () => {
            mobileNavToggle.setAttribute("aria-expanded", "false");
            mobileNavToggle.setAttribute("aria-label", "Open navigation");
            mobileNavToggle.querySelector("i").className = "bi bi-list";
            sidebar.classList.remove("is-open");
        });
    });

    loadFavorites();
    loadWorldWeather();
    searchForm.requestSubmit();

    window.setInterval(() => {
        if (document.hidden || !lastSearchedCity) return;

        weatherCache.clear();
        loadWeather(lastSearchedCity, lastSearchedCountry, true);
        favoritesList.querySelectorAll(".favorite-card").forEach(updateFavoriteWeather);
        loadWorldWeather(true);
    }, WEATHER_CACHE_DURATION);
})();
