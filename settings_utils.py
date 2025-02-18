import json
from pathlib import Path
import streamlit as st
import datetime

SETTINGS_FILE = "saved_settings.json"


def load_settings():
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


def save_settings(settings):
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


def validate_settings(settings, validate_required=False):
    """
    Validate settings dictionary

    Args:
        settings (dict): Settings dictionary to validate
        validate_required (bool): If True, validates all required fields must be present
                                If False, allows empty fields for saving settings
    """
    try:
        # Basic structure validation
        required_keys = [
            "valuation_date",
            "models_url",
            "model_name",
            "assumption_table_url",
            "model_point_files_url",
            "projection_period",
            "product_groups",
            "output_s3_url",
        ]

        missing_keys = [key for key in required_keys if key not in settings]
        if missing_keys:
            raise ValueError(f"Missing required settings: {', '.join(missing_keys)}")

        # Only validate non-empty values if validate_required is True
        if validate_required:
            # Validate models URL
            if not settings["models_url"]:
                raise ValueError("Models URL must be provided")
            if not settings["models_url"].startswith("s3://"):
                raise ValueError("Invalid models URL format. Must start with 's3://'")

            # Validate model selection
            if not settings["model_name"]:
                raise ValueError("A model must be selected")
            if isinstance(settings["model_name"], list):
                if len(settings["model_name"]) != 1:
                    raise ValueError("Please select exactly one model")
                settings["model_name"] = settings["model_name"][
                    0
                ]  # Convert list to single value

            # Validate S3 URLs
            s3_urls = [
                ("assumption_table_url", settings["assumption_table_url"]),
                ("model_point_files_url", settings["model_point_files_url"]),
                ("output_s3_url", settings["output_s3_url"]),
            ]

            for url_name, url in s3_urls:
                if not url:
                    raise ValueError(f"Missing required S3 URL for {url_name}")
                if not url.startswith("s3://"):
                    raise ValueError(f"Invalid S3 URL format for {url_name}: {url}")

            # Validate product groups
            if not settings["product_groups"]:
                raise ValueError("At least one product group must be selected")

            # Validate projection period
            if settings["projection_period"] < 1:
                raise ValueError("Projection period must be at least 1 year")

        return True

    except Exception as e:
        raise ValueError(f"Settings validation failed: {str(e)}")
