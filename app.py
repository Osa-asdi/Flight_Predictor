import calendar
import math
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
MODEL_PATH = BASE_DIR / "models" / "xgb_model_airport_5.pkl"
FEATURES = (
    "Unnamed: 0",
    "YEAR",
    "MONTH_NUM",
    "WEEKDAY",
    "DAY",
    "ELEVATION",
    "LATITUDE",
    "LONGITUDE",
    "STATE_NAME",
)

# Encodings reconstructed from the airport traffic data used by the current model.
COUNTRY_ENCODINGS = {
    "Spain": 0,
    "United Kingdom": 1,
    "Germany": 2,
    "France": 3,
    "Italy": 4,
    "Türkiye": 5,
    "Norway": 6,
    "Greece": 7,
    "Netherlands": 8,
    "Portugal": 9,
    "Switzerland": 10,
    "Poland": 11,
    "Austria": 12,
    "Belgium": 13,
    "Sweden": 14,
    "Ireland": 15,
    "Denmark": 16,
    "Finland": 17,
    "Morocco": 18,
    "Czech Republic": 19,
    "Romania": 20,
    "Hungary": 21,
    "Cyprus": 23,
    "Serbia": 24,
    "Luxembourg": 25,
    "Latvia": 26,
    "Malta": 27,
    "Bulgaria": 28,
    "Lithuania": 29,
    "Ukraine": 30,
    "Georgia": 31,
    "Croatia": 32,
    "Albania": 33,
    "Estonia": 34,
    "Armenia": 35,
    "Moldova": 36,
    "Slovenia": 37,
    "Slovakia": 38,
    "Iceland": 39,
    "Republic of North Macedonia": 40,
    "Montenegro": 41,
    "Bosnia and Herzegovina": 42,
}

app = Flask(__name__)
MODEL = joblib.load(MODEL_PATH)

model_features = getattr(MODEL, "feature_names_in_", None)
if model_features is None or tuple(model_features) != FEATURES:
    raise RuntimeError(
        f"Unexpected feature names in {MODEL_PATH.name}: {model_features!r}"
    )


class InvalidPredictionInput(ValueError):
    pass


def _finite_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidPredictionInput(f"'{field}' must be a number.")
    try:
        number = float(value)
    except OverflowError as exc:
        raise InvalidPredictionInput(f"'{field}' must be finite.") from exc
    if not math.isfinite(number):
        raise InvalidPredictionInput(f"'{field}' must be finite.")
    return number


def _parse_prediction_input(
    payload: dict[str, Any],
) -> tuple[date, str, float, float, float, str]:
    date_value = payload.get("date")
    if (
        not isinstance(date_value, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value) is None
    ):
        raise InvalidPredictionInput("'date' must use the YYYY-MM-DD format.")
    try:
        prediction_date = date.fromisoformat(date_value)
    except ValueError as exc:
        raise InvalidPredictionInput("'date' must be a valid calendar date.") from exc

    country = payload.get("country")
    if not isinstance(country, str) or country not in COUNTRY_ENCODINGS:
        raise InvalidPredictionInput("'country' must be one of the supported countries.")

    latitude = _finite_number(payload, "latitude")
    if not -90 <= latitude <= 90:
        raise InvalidPredictionInput("'latitude' must be between -90 and 90.")

    longitude = _finite_number(payload, "longitude")
    if not -180 <= longitude <= 180:
        raise InvalidPredictionInput("'longitude' must be between -180 and 180.")

    elevation_ft = _finite_number(payload, "elevation_ft")
    period = payload.get("period", "daily")
    if not isinstance(period, str) or period not in {"daily", "monthly", "yearly"}:
        raise InvalidPredictionInput("'period' must be daily, monthly, or yearly.")

    return prediction_date, country, latitude, longitude, elevation_ft, period


def _build_features(
    prediction_dates: pd.DatetimeIndex,
    country: str,
    latitude: float,
    longitude: float,
    elevation_ft: float,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Unnamed: 0": np.full(len(prediction_dates), np.nan),
            "YEAR": prediction_dates.year,
            "MONTH_NUM": prediction_dates.month,
            "WEEKDAY": (prediction_dates.dayofweek + 2) % 7,
            "DAY": prediction_dates.day,
            "ELEVATION": elevation_ft,
            "LATITUDE": latitude,
            "LONGITUDE": longitude,
            "STATE_NAME": COUNTRY_ENCODINGS[country],
        },
        columns=FEATURES,
    )


@app.get("/")
def index():
    return render_template(
        "index.html",
        countries=COUNTRY_ENCODINGS,
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY", ""),
    )


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "model": MODEL_PATH.name})


@app.post("/api/predict")
def predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Expected a JSON object in the request body."}), 400

    try:
        prediction_date, country, latitude, longitude, elevation_ft, period = (
            _parse_prediction_input(payload)
        )
    except InvalidPredictionInput as exc:
        return jsonify({"error": str(exc)}), 400

    if period == "daily":
        start = end = prediction_date
    elif period == "monthly":
        start = prediction_date.replace(day=1)
        end = date(
            prediction_date.year,
            prediction_date.month,
            calendar.monthrange(prediction_date.year, prediction_date.month)[1],
        )
    else:
        start = date(prediction_date.year, 1, 1)
        end = date(prediction_date.year, 12, 31)

    prediction_dates = pd.date_range(start=start, end=end, freq="D")
    features = _build_features(
        prediction_dates, country, latitude, longitude, elevation_ft
    )
    predictions = np.asarray(MODEL.predict(features), dtype=float)
    if not np.isfinite(predictions).all():
        app.logger.error("Model returned non-finite predictions for %s", period)
        return jsonify({"error": "The model returned an invalid prediction."}), 500

    weekday = (prediction_date.weekday() + 2) % 7
    base_response = {
        "period": period,
        "inputs": {
            "date": prediction_date.isoformat(),
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
            "elevation_ft": elevation_ft,
            "weekday_index": weekday,
        },
    }

    if period == "daily":
        predicted_flights = float(predictions[0])
        base_response.update(
            {
                "predicted_daily_flights": predicted_flights,
                "predicted_flights_rounded": int(round(predicted_flights)),
            }
        )
        return jsonify(base_response)

    daily_series = pd.DataFrame(
        {"date": prediction_dates, "predicted_flights": predictions}
    )
    if period == "monthly":
        series = [
            {
                "label": f"{day.strftime('%b')} {day.day}",
                "date": day.date().isoformat(),
                "predicted_flights": float(value),
                "predicted_flights_rounded": int(round(value)),
            }
            for day, value in zip(
                daily_series["date"], daily_series["predicted_flights"]
            )
        ]
        period_label = prediction_date.strftime("%B %Y")
    else:
        monthly_series = daily_series.assign(
            month=daily_series["date"].dt.month
        ).groupby("month", sort=True)["predicted_flights"].sum()
        series = [
            {
                "label": date(prediction_date.year, month, 1).strftime("%b"),
                "month": int(month),
                "predicted_flights": float(value),
                "predicted_flights_rounded": int(round(value)),
            }
            for month, value in monthly_series.items()
        ]
        period_label = str(prediction_date.year)

    total_flights = float(predictions.sum())
    base_response.update(
        {
            "period_label": period_label,
            "predicted_flights": total_flights,
            "predicted_flights_rounded": int(round(total_flights)),
            "series": series,
        }
    )
    return jsonify(base_response)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5005")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
