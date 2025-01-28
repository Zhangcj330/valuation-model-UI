import pandas as pd
import modelx as mx
from s3_utils import download_from_s3

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
    model_point_file = download_from_s3(model_points_url)
    return pd.read_excel(model_point_file, sheet_name='MPF')

def initialize_model(settings, assumptions, model_points_df):
    """Initialize and configure the modelx model"""
    model = mx.read_model("Basic_Term_Model_v1")
    model.Data_Inputs.proj_period = settings["projection_period"]
    model.Data_Inputs.val_date = settings["valuation_date"]
    model.assumptions = assumptions
    model.model_points = model_points_df
    return model

def run_model_calculations(model, product_groups):
    """Run calculations for each product group"""
    results = {}
    for product in product_groups:
        model.product = product
        results[product] = {
            'present_value': model.Results_at_t.aggregate_pvs(),
            'cashflows': model.Results_at_t.aggregate_cfs(),
            'analytic': model.Results_at_t.analytic() 
        }
    
    return results 