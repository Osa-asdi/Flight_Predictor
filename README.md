# Airport Traffic Predictor

This Flask application serves the airport-traffic prediction project using only
`models/xgb_model_airport_5.pkl`. It accepts a date, country, elevation, and
coordinates and returns a daily total-flight estimate. The browser map uses the
Google Maps JavaScript API; selecting a point also looks up its elevation.

## Run locally

Install the dependencies into the Python environment you want to use:

```powershell
python -m pip install -r requirements.txt
```

Set `GOOGLE_MAPS_API_KEY` in the project-root `.env` file; the app loads it
automatically. Alternatively, set it in your shell. The key must have the Maps
JavaScript API, Elevation API, and Geocoding API enabled. The Geocoding API is
needed to detect a country from the selected map location. Restrict the key to
the local site
(`http://127.0.0.1:5005/*` and `http://localhost:5005/*`) and to those APIs.
The `.env` file is ignored by Git; do not put the key in tracked source files.

```powershell
# Optional alternative to the .env file:
$env:GOOGLE_MAPS_API_KEY = "your-restricted-browser-key"
python app.py
```

Open `http://127.0.0.1:5005`. Without the key, the prediction API still works,
but the Google map and automatic lookups are unavailable. Elevation can also be
entered manually in feet. The selected location automatically fills its
elevation and, when supported by the model, its country. Country lookup requires
the Geocoding API; if it is unavailable or the location is outside the model's
supported countries, choose a country manually.

## API

`GET /api/health` reports whether the application started with the selected
model loaded.

`POST /api/predict` accepts JSON:

```json
{
  "date": "2026-06-15",
  "period": "monthly",
  "country": "United Kingdom",
  "latitude": 51.5072,
  "longitude": -0.1276,
  "elevation_ft": 100
}
```

The `period` can be `daily` (the default), `monthly`, or `yearly`. Monthly
forecasts return one estimate per day and the sum for the month; yearly forecasts
return one total per month and the sum for the year. The browser displays a chart
only for monthly and yearly forecasts.

The weekday feature uses the notebook's convention: Saturday is `0`, Sunday is
`1`, and Friday is `6`. The country codes are reconstructed from the current
airport traffic CSVs; they differ from the mapping displayed in the notebook.
The model also expects an `Unnamed: 0` CSV-index feature. Since a new prediction
has no corresponding training-row index, the API supplies that feature as
missing rather than inventing an index.

Install model and Flask dependencies from `requirements.txt`; the model is
loaded from the fixed path `models/xgb_model_airport_5.pkl`.
