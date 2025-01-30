import json
from pathlib import Path
import datetime

def load_settings():
    """Load saved settings from a JSON file"""
    settings_file = Path("saved_settings.json")
    if not settings_file.exists():
        return None
        
    with open(settings_file, "r") as f:
        settings = json.load(f)
        if isinstance(settings.get("valuation_date"), str):
            settings["valuation_date"] = datetime.datetime.strptime(
                settings["valuation_date"], "%Y-%m-%d"
            ).date()
        return settings

def save_settings(settings):
    """Save settings to a JSON file"""
    settings_file = Path("saved_settings.json")
    settings["valuation_date"] = settings["valuation_date"].isoformat()
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

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
            "output_s3_url"
        ]
        
        missing_keys = [key for key in required_keys if key not in settings]
        if missing_keys:
            raise ValueError(f"Missing required settings: {', '.join(missing_keys)}")
            
        # Only validate non-empty values if validate_required is True
        if validate_required:
            # Validate models URL
            if not settings["models_url"]:
                raise ValueError("Models URL must be provided")
            if not settings["models_url"].startswith('s3://'):
                raise ValueError("Invalid models URL format. Must start with 's3://'")
            
            # Validate model selection
            if not settings["model_name"]:
                raise ValueError("A model must be selected")
            if isinstance(settings["model_name"], list):
                if len(settings["model_name"]) != 1:
                    raise ValueError("Please select exactly one model")
                settings["model_name"] = settings["model_name"][0]  # Convert list to single value
            
            # Validate S3 URLs
            s3_urls = [
                ("assumption_table_url", settings["assumption_table_url"]),
                ("model_point_files_url", settings["model_point_files_url"]),
                ("output_s3_url", settings["output_s3_url"])
            ]
            
            for url_name, url in s3_urls:
                if not url:
                    raise ValueError(f"Missing required S3 URL for {url_name}")
                if not url.startswith('s3://'):
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