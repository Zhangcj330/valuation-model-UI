import json
from pathlib import Path
import streamlit as st
import datetime
from typing import List

SETTINGS_FILE = "saved_settings.json"


class ModelSettings:
    def __init__(
        self,
        assumption_url: str,
        models_url: str,
        model_points_url: str,
        results_url: str,
        valuation_date: datetime.date,
        projection_period: int,
        product_groups: List[str],
        model_name: str,
        run_number: int = 1,
    ):
        self.assumption_url = assumption_url
        self.models_url = models_url
        self.model_points_url = model_points_url
        self.results_url = results_url
        self.valuation_date = valuation_date
        self.projection_period = projection_period
        self.product_groups = product_groups
        self.model_name = model_name
        self.run_number = run_number

    def validate(self, validate_required=False):
        """Validate the settings to ensure all required fields are set correctly."""
        required_keys = [
            "assumption_url",
            "models_url",
            "model_points_url",
            "results_url",
            "valuation_date",
            "projection_period",
            "product_groups",
            "model_name",
        ]

        # Check for missing keys
        missing_keys = [key for key in required_keys if getattr(self, key) is None]
        if missing_keys:
            raise ValueError(f"Missing required settings: {', '.join(missing_keys)}")

        # Validate required fields if specified
        if validate_required:
            if not self.assumption_url:
                raise ValueError("Assumption URL is required.")
            if not self.models_url:
                raise ValueError("Models URL is required.")
            if not self.model_points_url:
                raise ValueError("Model Points URL is required.")
            if not self.results_url:
                raise ValueError("Results URL is required.")
            if not isinstance(self.valuation_date, datetime.date):
                raise ValueError("Valuation date must be a datetime.date object.")
            if (
                not isinstance(self.projection_period, int)
                or self.projection_period <= 0
            ):
                raise ValueError("Projection period must be a positive integer.")
            if not self.product_groups or not isinstance(self.product_groups, list):
                raise ValueError("Product groups must be a non-empty list.")

            # Validate URLs based on storage type
            storage_type = st.session_state.get("storage_type", "S3")
            url_fields = [
                "assumption_url",
                "models_url",
                "model_points_url",
                "results_url",
            ]

            for url_field in url_fields:
                url = getattr(self, url_field)
                if not url:
                    raise ValueError(f"Missing required URL for {url_field}")

                if storage_type == "S3" and not url.startswith("s3://"):
                    raise ValueError(f"Invalid S3 URL format for {url_field}: {url}")

                # Add SharePoint-specific URL validation if needed

            # Validate model selection
            if not self.model_name:
                raise ValueError("A model must be selected")
            if isinstance(self.model_name, list):
                if len(self.model_name) != 1:
                    raise ValueError("Please select exactly one model")
                self.model_name = self.model_name[0]

            # Validate product groups
            if not self.product_groups:
                raise ValueError("At least one product group must be selected")

            # Validate projection period
            if self.projection_period < 1:
                raise ValueError("Projection period must be at least 1 year")

    @classmethod
    def from_dict(cls, data: dict):
        """Create a ModelSettings object from a dictionary."""
        valuation_date = data.get("valuation_date")
        if isinstance(valuation_date, str):
            valuation_date = datetime.datetime.strptime(
                valuation_date, "%Y-%m-%d"
            ).date()

        return cls(
            assumption_url=data.get("assumption_url", ""),
            models_url=data.get("models_url", ""),
            model_points_url=data.get("model_points_url", ""),
            results_url=data.get("results_url", ""),
            valuation_date=valuation_date,
            projection_period=int(data.get("projection_period", 0)),
            product_groups=data.get("product_groups", []),
            model_name=data.get("model_name"),
        )

    def to_dict(self):
        """Convert the ModelSettings object to a dictionary."""
        return {
            "assumption_url": self.assumption_url,
            "models_url": self.models_url,
            "model_points_url": self.model_points_url,
            "results_url": self.results_url,
            "valuation_date": self.valuation_date.isoformat(),
            "projection_period": self.projection_period,
            "product_groups": self.product_groups,
            "model_name": self.model_name,
        }


def load_config():
    """Load saved settings from file"""
    try:
        settings_path = Path(SETTINGS_FILE)
        if not settings_path.exists():
            return {}

        with open(settings_path, "r") as f:
            try:
                settings = json.load(f)
                if isinstance(settings.get("valuation_date"), str):
                    settings["valuation_date"] = datetime.datetime.strptime(
                        settings["valuation_date"], "%Y-%m-%d"
                    ).date()
                return settings
            except json.JSONDecodeError:
                # 如果JSON解析失败，返回空字典
                return {}

    except Exception as e:
        st.warning(f"Error loading settings: {str(e)}")
        return {}


def save_config(settings):
    """Save settings to file"""
    try:
        # 确保所有值都是JSON可序列化的
        serializable_settings = {}
        for key, value in settings.items():
            if hasattr(value, "isoformat"):  # 处理日期对象
                serializable_settings[key] = value.isoformat()
            elif isinstance(value, (list, dict, str, int, float, bool, type(None))):
                serializable_settings[key] = value
            else:
                serializable_settings[key] = str(value)

        with open(SETTINGS_FILE, "w") as f:
            json.dump(serializable_settings, f, indent=4)

    except Exception as e:
        st.error(f"Error saving settings: {str(e)}")
        raise
