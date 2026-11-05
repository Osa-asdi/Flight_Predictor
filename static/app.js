const form = document.querySelector("#prediction-form");
const submitButton = document.querySelector("#submit-button");
const formError = document.querySelector("#form-error");
const result = document.querySelector("#result");
const predictionValue = document.querySelector("#prediction-value");
const predictionContext = document.querySelector("#prediction-context");
const periodSelect = document.querySelector("#period");
const dateHelp = document.querySelector("#date-help");
const chartCard = document.querySelector("#chart-card");
const chartHeading = document.querySelector("#chart-heading");
const chartDescription = document.querySelector("#chart-description");
const chartCanvas = document.querySelector("#prediction-chart");
const mapStatus = document.querySelector("#map-status");
const latitudeInput = document.querySelector("#latitude");
const longitudeInput = document.querySelector("#longitude");
const elevationInput = document.querySelector("#elevation_ft");
const countrySelect = document.querySelector("#country");

const localDate = new Date();
const localYear = localDate.getFullYear();
const localMonth = String(localDate.getMonth() + 1).padStart(2, "0");
const localDay = String(localDate.getDate()).padStart(2, "0");
document.querySelector("#date").value = `${localYear}-${localMonth}-${localDay}`;

function updatePeriodControls() {
  const period = periodSelect.value;
  const descriptions = {
    daily: "The selected date is used for a daily forecast.",
    monthly: "The selected month is forecast day by day; its daily estimates are summed.",
    yearly: "The selected year is forecast month by month; each month sums its daily estimates.",
  };
  dateHelp.textContent = descriptions[period];
  submitButton.textContent = `Predict ${period} flights`;
  result.hidden = true;
  chartCard.hidden = true;
  lastChart = null;
}

periodSelect.addEventListener("change", updatePeriodControls);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;
  result.hidden = true;
  chartCard.hidden = true;
  lastChart = null;
  submitButton.disabled = true;
  submitButton.textContent = "Predicting…";

  const payload = {
    date: document.querySelector("#date").value,
    period: periodSelect.value,
    country: document.querySelector("#country").value,
    latitude: Number(latitudeInput.value),
    longitude: Number(longitudeInput.value),
    elevation_ft: Number(elevationInput.value),
  };

  try {
    const response = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "The prediction request failed.");
    }

    predictionValue.textContent = new Intl.NumberFormat().format(
      body.predicted_flights_rounded,
    );
    result.querySelector(".eyebrow").textContent =
      body.period === "daily"
        ? "Estimated flights for the day"
        : `Estimated flights for ${body.period_label}`;
    predictionContext.textContent =
      `${body.inputs.country} · ${body.period_label || body.inputs.date} · ` +
      `${body.inputs.latitude.toFixed(5)}, ${body.inputs.longitude.toFixed(5)}`;
    result.hidden = false;
    if (body.period !== "daily") {
      showPredictionChart(body);
    }
  } catch (error) {
    formError.textContent = error.message || "Unable to get a prediction.";
    formError.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = `Predict ${periodSelect.value} flights`;
  }
});

let lastChart = null;

function showPredictionChart(body) {
  lastChart = body;
  chartHeading.textContent =
    body.period === "monthly" ? "Daily predictions for the month" : "Monthly predictions for the year";
  chartDescription.textContent =
    body.period === "monthly"
      ? `${body.period_label} · each point is the predicted daily total.`
      : `${body.period_label} · each bar is the predicted monthly total.`;
  chartCanvas.setAttribute(
    "aria-label",
    `${chartHeading.textContent}: ${body.series
      .map((point) => `${point.label}: ${point.predicted_flights_rounded} flights`)
      .join(", ")}`,
  );
  chartCard.hidden = false;
  drawPredictionChart(body.series, body.period);
}

function drawPredictionChart(series, period) {
  const context = chartCanvas.getContext("2d");
  if (!context) {
    formError.textContent = "Your browser could not draw the prediction chart.";
    formError.hidden = false;
    chartCard.hidden = true;
    return;
  }

  const width = chartCanvas.clientWidth;
  const height = 340;
  const pixelRatio = window.devicePixelRatio || 1;
  chartCanvas.width = width * pixelRatio;
  chartCanvas.height = height * pixelRatio;
  context.scale(pixelRatio, pixelRatio);

  const padding = { top: 22, right: 20, bottom: 58, left: 68 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const values = series.map((point) => point.predicted_flights);
  const maximum = Math.max(...values, 1);
  const tickStep = maximum / 4;
  const x = (index) =>
    padding.left + (series.length === 1 ? plotWidth / 2 : (index / (series.length - 1)) * plotWidth);
  const y = (value) => padding.top + plotHeight - (value / maximum) * plotHeight;

  context.clearRect(0, 0, width, height);
  context.font = "12px Segoe UI, sans-serif";
  context.lineWidth = 1;
  context.textAlign = "right";
  context.textBaseline = "middle";
  for (let tick = 0; tick <= 4; tick += 1) {
    const value = tickStep * tick;
    const tickY = y(value);
    context.strokeStyle = "#e7edf5";
    context.beginPath();
    context.moveTo(padding.left, tickY);
    context.lineTo(width - padding.right, tickY);
    context.stroke();
    context.fillStyle = "#63718a";
    context.fillText(new Intl.NumberFormat().format(Math.round(value)), padding.left - 10, tickY);
  }

  context.strokeStyle = "#3867d6";
  context.fillStyle = "#3867d6";
  context.lineWidth = 2.5;
  if (period === "yearly") {
    const slot = plotWidth / series.length;
    const barWidth = Math.min(34, slot * 0.62);
    series.forEach((point, index) => {
      const barY = y(point.predicted_flights);
      context.fillRect(x(index) - barWidth / 2, barY, barWidth, padding.top + plotHeight - barY);
    });
  } else {
    series.forEach((point, index) => {
      if (index === 0) {
        context.beginPath();
        context.moveTo(x(index), y(point.predicted_flights));
      } else {
        context.lineTo(x(index), y(point.predicted_flights));
      }
    });
    context.stroke();
  }

  const labelIndexes = period === "yearly"
    ? series.map((_, index) => index)
    : series
        .map((point, index) => ({ point, index }))
        .filter(({ point }) => {
          const day = Number(point.date.slice(-2));
          return day === 1 || day % 5 === 0 || day === series.length;
        })
        .map(({ index }) => index);
  context.fillStyle = "#63718a";
  context.textAlign = "center";
  context.textBaseline = "top";
  labelIndexes.forEach((index) => {
    context.fillText(series[index].label, x(index), padding.top + plotHeight + 12);
  });
}

const chartResizeObserver = new ResizeObserver(() => {
  if (!chartCard.hidden && lastChart) {
    drawPredictionChart(lastChart.series, lastChart.period);
  }
});
chartResizeObserver.observe(chartCanvas);

const countryByRegionCode = {
  AL: "Albania",
  AM: "Armenia",
  AT: "Austria",
  BA: "Bosnia and Herzegovina",
  BE: "Belgium",
  BG: "Bulgaria",
  CH: "Switzerland",
  CY: "Cyprus",
  CZ: "Czech Republic",
  DE: "Germany",
  DK: "Denmark",
  EE: "Estonia",
  ES: "Spain",
  FI: "Finland",
  FR: "France",
  GB: "United Kingdom",
  GE: "Georgia",
  GR: "Greece",
  HR: "Croatia",
  HU: "Hungary",
  IE: "Ireland",
  IS: "Iceland",
  IT: "Italy",
  LT: "Lithuania",
  LU: "Luxembourg",
  LV: "Latvia",
  MA: "Morocco",
  MD: "Moldova",
  ME: "Montenegro",
  MK: "Republic of North Macedonia",
  MT: "Malta",
  NL: "Netherlands",
  NO: "Norway",
  PL: "Poland",
  PT: "Portugal",
  RO: "Romania",
  RS: "Serbia",
  SE: "Sweden",
  SI: "Slovenia",
  SK: "Slovakia",
  TR: "Türkiye",
  UA: "Ukraine",
};

let elevationService;
let geocoder;
let locationLookupId = 0;
let elevationLookupMessage = "";
let countryLookupMessage = "";

function updateLookupStatus(id, lookupType, message) {
  if (id !== locationLookupId) {
    return;
  }
  if (lookupType === "elevation") {
    elevationLookupMessage = message;
  } else {
    countryLookupMessage = message;
  }
  mapStatus.textContent = [countryLookupMessage, elevationLookupMessage]
    .filter(Boolean)
    .join(" ");
}

function setCoordinates(position) {
  latitudeInput.value = position.lat().toFixed(6);
  longitudeInput.value = position.lng().toFixed(6);
  elevationInput.value = "";
  countrySelect.value = "";
  const id = ++locationLookupId;
  elevationLookupMessage = "";
  countryLookupMessage = "";
  mapStatus.textContent = "Looking up country and elevation…";
  updateElevation(position, id);
  updateCountry(position, id);
}

function updateElevation(position, id) {
  elevationService.getElevationForLocation({ location: position }, (results, status) => {
    if (id !== locationLookupId) {
      return;
    }
    if (status === "OK" && results && results[0]) {
      elevationInput.value = (results[0].elevation * 3.280839895).toFixed(1);
      updateLookupStatus(id, "elevation", "Elevation filled from the map.");
      return;
    }
    updateLookupStatus(
      id,
      "elevation",
      "Could not retrieve elevation; enter it in feet manually.",
    );
  });
}

function updateCountry(position, id) {
  geocoder.geocode({ location: position }, (results, status) => {
    if (id !== locationLookupId) {
      return;
    }
    if (status === "OK" && results) {
      const countryComponent = results
        .flatMap((result) => result.address_components || [])
        .find((component) => component.types.includes("country"));
      const country = countryComponent
        ? countryByRegionCode[countryComponent.short_name]
        : undefined;
      if (country && [...countrySelect.options].some((option) => option.value === country)) {
        countrySelect.value = country;
        updateLookupStatus(id, "country", `Country set to ${country}.`);
        return;
      }
      countrySelect.value = "";
      updateLookupStatus(
        id,
        "country",
        "This location is outside the model's supported countries; choose a country manually.",
      );
      return;
    }
    countrySelect.value = "";
    updateLookupStatus(
      id,
      "country",
      status === "REQUEST_DENIED"
        ? "Country lookup needs the Geocoding API enabled in Google Cloud; choose a country manually."
        : "Could not detect the country; choose it manually.",
    );
  });
}

window.initAirportMap = function initAirportMap() {
  const mapElement = document.querySelector("#map");
  const map = new google.maps.Map(mapElement, {
    center: { lat: 50, lng: 10 },
    zoom: 4,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
  });
  elevationService = new google.maps.ElevationService();
  geocoder = new google.maps.Geocoder();
  let marker = null;

  function chooseLocation(position) {
    if (marker) {
      marker.setPosition(position);
    } else {
      marker = new google.maps.Marker({
        map,
        position,
        draggable: true,
        title: "Selected airport location",
      });
      marker.addListener("dragend", () => setCoordinates(marker.getPosition()));
    }
    map.panTo(position);
    setCoordinates(position);
  }

  map.addListener("click", (event) => chooseLocation(event.latLng));
  mapStatus.textContent = "Click the map to choose an airport location.";

  function updateMarkerFromInputs() {
    const latitude = Number(latitudeInput.value);
    const longitude = Number(longitudeInput.value);
    if (
      latitudeInput.value === "" ||
      longitudeInput.value === "" ||
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      latitude < -90 ||
      latitude > 90 ||
      longitude < -180 ||
      longitude > 180
    ) {
      return;
    }
    chooseLocation(new google.maps.LatLng(latitude, longitude));
  }

  latitudeInput.addEventListener("change", updateMarkerFromInputs);
  longitudeInput.addEventListener("change", updateMarkerFromInputs);
};

const mapsApiKey = window.APP_CONFIG.googleMapsApiKey;
if (!mapsApiKey) {
  mapStatus.textContent =
    "Set GOOGLE_MAPS_API_KEY to enable the map and automatic elevation lookup.";
} else {
  window.gm_authFailure = () => {
    mapStatus.textContent = "Google Maps rejected the API key. Check its restrictions and enabled APIs.";
  };
  const mapsScript = document.createElement("script");
  mapsScript.src =
    "https://maps.googleapis.com/maps/api/js?" +
    new URLSearchParams({
      key: mapsApiKey,
      callback: "initAirportMap",
      loading: "async",
    });
  mapsScript.async = true;
  mapsScript.onerror = () => {
    mapStatus.textContent = "Google Maps could not be loaded. Check the API key and network.";
  };
  document.head.appendChild(mapsScript);
}
