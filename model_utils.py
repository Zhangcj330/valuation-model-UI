from re import M
import pandas as pd
import modelx as mx
from s3_utils import download_from_s3, download_and_validate_excel_files, get_foldernames_from_s3, download_folder_from_s3

import logging
from pathlib import Path


logger = logging.getLogger(__name__)

def load_assumptions(assumption_url):
    """Load assumption tables from S3"""
    assumption_file = download_from_s3(assumption_url)
    return {
        'lapse_rate_table': pd.read_excel(assumption_file, sheet_name='lapse'),
        'inflation_rate_table': pd.read_excel(assumption_file, sheet_name='CPI'),
        'prem_exp_table': pd.read_excel(assumption_file, sheet_name='prem expenses'),
        'fixed_exp_table': pd.read_excel(assumption_file, sheet_name='fixed expenses'),
        'comm_table': pd.read_excel(assumption_file, sheet_name='commissions'),
        'disc_curve': pd.read_excel(assumption_file, sheet_name='discount curve'),
        'mort_table': pd.read_excel(assumption_file, sheet_name='mortality'),
        'trauma_table': pd.read_excel(assumption_file, sheet_name='trauma'),
        'tpd_table': pd.read_excel(assumption_file, sheet_name='TPD'),
        'prem_rate_level_table': pd.read_excel(assumption_file, sheet_name='prem_rate_level'),
        'prem_rate_stepped_table': pd.read_excel(assumption_file, sheet_name='prem_rate_stepped'),
        'RA_table': pd.read_excel(assumption_file, sheet_name='RA'),
        'RI_prem_rate_level_table': pd.read_excel(assumption_file, sheet_name='RI_prem_rate_level'),
        'RI_prem_rate_stepped_table': pd.read_excel(assumption_file, sheet_name='RI_prem_rate_stepped')
    }

def load_model_points(model_points_url):
    """Load model points from S3"""
    model_point_files = download_and_validate_excel_files(model_points_url)
    if isinstance(model_point_files, list):
        if len(model_point_files) == 0:
            raise ValueError("No valid model point files found")
        return model_point_files
    return [model_point_files]  # Return as list for consistent handling

def get_available_models(s3_models_url):
    """Get list of available models from the models directory"""
    try:
        # Assuming models are in a 'models' directory
        model_names = get_foldernames_from_s3(s3_models_url)
        model_dir = Path("models")

        if not model_dir.exists():
            raise ValueError("Models directory not found")
            
        # Get all directories in the models folder
        models = [d.name for d in model_dir.iterdir() if d.is_dir()]
        if not models:
            raise ValueError("No models found in models directory")
            
        return sorted(models)  # Return sorted list of model names
    except Exception as e:
        logger.error(f"Error getting available models: {str(e)}")
        raise

def initialize_model(settings, assumptions, model_points_df):
    """Initialize and configure the modelx model"""
    model_name = settings.get("model_name")
    if not model_name:
        raise ValueError("Model name not specified in settings")
    
    model_path = settings.get('models_url')
    
    download_folder_from_s3(model_path, model_name, "./tmp")
    model = mx.read_model("./tmp")
    model.Data_Inputs.proj_period = settings["projection_period"]
    model.Data_Inputs.val_date = settings["valuation_date"]
    model.assumptions = assumptions
    model.model_point_table = model_points_df
    return model

def process_all_model_points(settings, assumptions, model_points_list):
    """Process all model point files and return combined results"""
    all_results = {}
    
    for model_points_df in model_points_list:
        # Initialize model for this set of model points
        model = initialize_model(settings, assumptions, model_points_df)
        
        # Run calculations
        results = run_model_calculations(model, settings["product_groups"])
        
        # Generate unique identifier for this model point set
        # You might want to extract this from the DataFrame or use another method
        model_point_id = model_points_df.get('model_point_set_id', '').iloc[0] if 'model_point_set_id' in model_points_df.columns else f"set_{len(all_results)}"
        
        all_results[model_point_id] = results
        
    return all_results

def run_model_calculations(model, product_groups):
    """Run calculations for each product group"""
    results = {}
    for product in product_groups:
        model.product = product
        results[product] = {
            'present_value': model.Results.pv_results(0),
            'analytics': model.Results.analytics() 
        }
    
    return results 