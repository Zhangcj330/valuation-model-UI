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

def validate_settings(settings):
    """Validate user input settings"""
    if not settings["product_groups"]:
        raise ValueError("Please select at least one product group")
        
    if not all([settings["assumption_table_url"], settings["model_point_files_url"]]):
        raise ValueError("Please provide all S3 URLs")
        
    for url in [settings["assumption_table_url"], settings["model_point_files_url"]]:
        if not url.startswith('s3://'):
            raise ValueError(f"Invalid S3 URL format: {url}")
    
    return True 