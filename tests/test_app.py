import os
import unittest
from unittest.mock import patch

import numpy as np

import app


class PredictionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_health_reports_selected_model(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "ok", "model": "xgb_model_airport_5.pkl"},
        )

    def test_index_passes_google_maps_key_to_page(self):
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-browser-key"}):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('googleMapsApiKey: "test-browser-key"', response.get_data(as_text=True))

    def test_prediction_uses_model_feature_order_and_weekday_convention(self):
        with patch.object(app.MODEL, "predict", return_value=np.array([42.25])) as predict:
            response = self.client.post(
                "/api/predict",
                json={
                    "date": "2025-06-15",
                    "country": "United Kingdom",
                    "latitude": 51.5072,
                    "longitude": -0.1276,
                    "elevation_ft": 100,
                },
            )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["predicted_flights_rounded"], 42)
        self.assertEqual(result["inputs"]["weekday_index"], 1)

        features = predict.call_args.args[0]
        self.assertEqual(tuple(features.columns), app.FEATURES)
        self.assertTrue(np.isnan(features.loc[0, "Unnamed: 0"]))
        self.assertEqual(features.loc[0, "STATE_NAME"], 1)
        self.assertEqual(features.loc[0, "DAY"], 15)

    def test_invalid_date_is_rejected(self):
        response = self.client.post(
            "/api/predict",
            json={
                "date": "2025-02-30",
                "country": "United Kingdom",
                "latitude": 51.5,
                "longitude": -0.1,
                "elevation_ft": 100,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid calendar date", response.get_json()["error"])

    def test_invalid_coordinates_are_rejected(self):
        response = self.client.post(
            "/api/predict",
            json={
                "date": "2025-06-15",
                "country": "United Kingdom",
                "latitude": 91,
                "longitude": -0.1,
                "elevation_ft": 100,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("latitude", response.get_json()["error"])

    def test_non_finite_elevation_is_rejected(self):
        response = self.client.post(
            "/api/predict",
            json={
                "date": "2025-06-15",
                "country": "United Kingdom",
                "latitude": 51.5,
                "longitude": -0.1,
                "elevation_ft": 10**400,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("finite", response.get_json()["error"])

    def test_monthly_prediction_returns_daily_series_and_month_total(self):
        with patch.object(app.MODEL, "predict", return_value=np.full(29, 2.0)) as predict:
            response = self.client.post(
                "/api/predict",
                json={
                    "date": "2024-02-15",
                    "period": "monthly",
                    "country": "United Kingdom",
                    "latitude": 51.5072,
                    "longitude": -0.1276,
                    "elevation_ft": 100,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["period_label"], "February 2024")
        self.assertEqual(body["predicted_flights_rounded"], 58)
        self.assertEqual(len(body["series"]), 29)
        self.assertEqual(body["series"][0]["date"], "2024-02-01")
        self.assertEqual(body["series"][-1]["date"], "2024-02-29")
        self.assertEqual(len(predict.call_args.args[0]), 29)

    def test_yearly_prediction_returns_twelve_month_totals(self):
        with patch.object(app.MODEL, "predict", return_value=np.ones(366)) as predict:
            response = self.client.post(
                "/api/predict",
                json={
                    "date": "2024-06-15",
                    "period": "yearly",
                    "country": "United Kingdom",
                    "latitude": 51.5072,
                    "longitude": -0.1276,
                    "elevation_ft": 100,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["period_label"], "2024")
        self.assertEqual(body["predicted_flights_rounded"], 366)
        self.assertEqual(len(body["series"]), 12)
        self.assertEqual(body["series"][1]["label"], "Feb")
        self.assertEqual(body["series"][1]["predicted_flights_rounded"], 29)
        self.assertEqual(len(predict.call_args.args[0]), 366)

    def test_unknown_prediction_period_is_rejected(self):
        response = self.client.post(
            "/api/predict",
            json={
                "date": "2025-06-15",
                "period": "weekly",
                "country": "United Kingdom",
                "latitude": 51.5,
                "longitude": -0.1,
                "elevation_ft": 100,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("period", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
