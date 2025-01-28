import pandas as pd
import modelx as mx
from s3_utils import download_from_s3, download_and_validate_excel_files, upload_to_s3
import os
from datetime import datetime
import json
import logging

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
        'mort_table': pd.read_excel(assumption_file, sheet_name='mortality')
    }

def load_model_points(model_points_url):
    """Load model points from S3"""
    model_point_files = download_and_validate_excel_files(model_points_url)
    if isinstance(model_point_files, list):
        if len(model_point_files) == 0:
            raise ValueError("No valid model point files found")
        return model_point_files
    return [model_point_files]  # Return as list for consistent handling

def initialize_model(settings, assumptions, model_points_df):
    """Initialize and configure the modelx model"""
    model = mx.read_model("Basic_Term_Model_v1")
    model.Data_Inputs.proj_period = settings["projection_period"]
    model.Data_Inputs.val_date = settings["valuation_date"]
    model.assumptions = assumptions
    model.model_points = model_points_df
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

def save_results_to_s3(results, model_points_url, output_s3_url):
    """Save model results to S3"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_locations = []
    
    # Save individual results for each model point set
    for model_point_id, model_results in results.items():
        # Create results dictionary with metadata
        results_with_metadata = {
            "timestamp": timestamp,
            "model_points_source": model_points_url,
            "model_point_set": model_point_id,
            "results": model_results
        }
        
        # Convert results to JSON
        results_json = json.dumps(results_with_metadata, default=str)
        
        # Generate output filename
        output_filename = f"results_{model_point_id}_{timestamp}.json"
        output_path = os.path.join(output_s3_url.rstrip('/'), output_filename)
        
        # Upload to S3
        upload_to_s3(results_json, output_path)
        saved_locations.append(output_path)
    
    return saved_locations

def run_model_calculations(model, product_groups):
    """Run calculations for each product group"""
    results = {}
    for product in product_groups:
        model.product = product
        results[product] = {
            'present_value': model.Results_at_t.aggregate_pvs(),
            'cashflows': model.Results_at_t.aggregate_cfs().to_dict(),  # Convert DataFrame to dict for JSON serialization
            'analytic': model.Results_at_t.analytic() 
        }
    
    return results 