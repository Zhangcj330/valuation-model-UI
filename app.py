import streamlit as st
import datetime
import os
import json
from pathlib import Path
import pandas as pd
import modelx as mx
import shutil


def load_settings():
    """Load saved settings from a JSON file"""
    settings_file = Path("saved_settings.json")
    if settings_file.exists():
        with open(settings_file, "r") as f:
            return json.load(f)
    return None

def save_settings(settings):
    """Save settings to a JSON file"""
    settings_file = Path("saved_settings.json")
    # Convert date to string for JSON serialization
    settings["valuation_date"] = settings["valuation_date"].isoformat()
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

def run_pricing_model(settings):
    """
    Run the pricing model using modelX lifelib with the provided settings
    """
    try:
        # Create isolated workspace for this specific model run
        work_dir = Path("work_dir")
        work_dir.mkdir(exist_ok=True)
        
        # Copy files to working directory to:
        # 1. Ensure file availability during processing
        # 2. Prevent modifications to original files
        # 3. Allow for file manipulation if needed
        assumption_dest = work_dir / Path(settings["assumption_table"]).name
        model_point_dest = work_dir / Path(settings["model_point_files"]).name
        
        shutil.copy2(settings["assumption_table"], assumption_dest)
        shutil.copy2(settings["model_point_files"], model_point_dest)
        
        # Read input files
        if assumption_dest.suffix == '.xlsx':
            assumptions = {
                'lapse_rate_table': pd.read_excel(assumption_dest, sheet_name='lapse'),
                'inflation_rate_table': pd.read_excel(assumption_dest, sheet_name='CPI'),
                'prem_exp_table': pd.read_excel(assumption_dest, sheet_name='prem expenses'),
                'fixed_exp_table': pd.read_excel(assumption_dest, sheet_name='fixed expenses'),
                'comm_table': pd.read_excel(assumption_dest, sheet_name='commissions'),
                'disc_curve': pd.read_excel(assumption_dest, sheet_name='discount curve'),
                'mort_table': pd.read_excel(assumption_dest, sheet_name='mortality')
            }
        else:
            raise ValueError("Assumptions file must be an Excel file (.xlsx)")

        # Read model points from separate Excel file
        model_points_df = pd.read_excel(model_point_dest, sheet_name='MPF') if model_point_dest.suffix == '.xlsx' \
            else pd.read_csv(model_point_dest)
        
        # Initialize modelx model
        model = mx.read_model("Basic_Term_Model_v1")
        
        # Configure model settings
        model.Data_Inputs.proj_period = settings["projection_period"]
        model.Data_Inputs.val_date = settings["valuation_date"]
        
        # Load assumptions and model points into the model
        model.Data_Inputs.lapse_rate_table = assumptions['lapse_rate_table']
        model.Data_Inputs.inflation_rate_table = assumptions['inflation_rate_table']
        model.Data_Inputs.prem_exp_table = assumptions['prem_exp_table']
        model.Data_Inputs.fixed_exp_table = assumptions['fixed_exp_table']
        model.Data_Inputs.comm_table = assumptions['comm_table']
        model.Data_Inputs.disc_curve = assumptions['disc_curve']
        model.Data_Inputs.mort_table = assumptions['mort_table']
        model.Data_Inputs.model_point_table = model_points_df
        
        results = {}
        # To do: Run model for each product group

        
        results = {
                'present_value': model.Results_at_t.aggregate_pvs(),
                'cashflows': model.Results_at_t.aggregate_cfs(),
                'analytic': model.Results_at_t.analytic() 
            }
     
        return {
            'status': 'success',
            'results': results,
            'message': 'Model run completed successfully'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error running model: {str(e)}'
        }
    finally:
        # Clean up: Remove all temporary files and the working directory
        # This prevents accumulation of temporary files
        if work_dir.exists():
            shutil.rmtree(work_dir)

def main():
    st.title("Enterprise Pricing Model Settings")
    
    # Load saved settings
    saved_settings = load_settings()
    
    # Add a settings management section
    with st.expander("Settings Management"):
        st.info("You can save your current settings or load previously saved settings.")
        if saved_settings:
            if st.button("Load Saved Settings"):
                # Convert saved date string back to datetime
                saved_settings["valuation_date"] = datetime.date.fromisoformat(
                    saved_settings["valuation_date"]
                )
                st.session_state.update(saved_settings)
                st.success("Settings loaded successfully!")
    
    # Create a form to collect all inputs
    with st.form("pricing_model_settings"):
        # Valuation Date
        val_date = st.date_input(
            "Valuation Date",
            value=saved_settings.get("valuation_date", datetime.date.today()) if saved_settings else datetime.date.today(),
            help="Select the valuation date for the pricing model"
        )
        
        # File/Directory Selection using file uploader
        st.subheader("File Locations")
        
        # Assumption Table
        st.markdown("##### Assumption Table Location")
        
        assumption_upload = st.file_uploader(
            "Upload assumption table",
            type=["xlsx", "csv"],
            key="assumption_upload"
        )
        if assumption_upload:
            assumption_table = os.path.join("uploads", assumption_upload.name)
            with open(assumption_table, "wb") as f:
                f.write(assumption_upload.getbuffer())
                    
        # Model Point Files
        st.markdown("##### Model Point Files Location")
    
        model_point_upload = st.file_uploader(
            "Upload model point files",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="model_point_upload"
        )
        if model_point_upload:
            model_point_files = os.path.join("uploads", model_point_upload[0].name)
            with open(model_point_files, "wb") as f:
                f.write(model_point_upload[0].getbuffer())

        # Projection Period
        projection_period = st.number_input(
            "Projection Period (Years)",
            min_value=1,
            max_value=100,
            value=saved_settings.get("projection_period", 30) if saved_settings else 30,
            help="Enter the number of years to project"
        )
        
        # Product Groups
        product_groups = st.multiselect(
            "Select Product Groups to Run",
            options=[
                "Term Life",
                "Whole Life",
                "Universal Life",
                "Annuities",
                "Group Insurance",
                "Disability Insurance"
            ],
            default=saved_settings.get("product_groups", []) if saved_settings else [],
            help="Choose one or more product groups to include in the run"
        )
        
        # Submit button
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Run Pricing Model")
        with col2:
            save_button = st.form_submit_button("Save Settings")
        
        if submitted or save_button:
            if not product_groups:
                st.error("Please select at least one product group")
                return
                
            if not all([assumption_table, model_point_files]):
                st.error("Please fill in all file locations")
                return
                
            # Validate paths
            for path in [assumption_table, model_point_files]:
                if not os.path.exists(path):
                    st.error(f"Path does not exist: {path}")
                    return
            
            # Collect settings
            run_settings = {
                "valuation_date": val_date,
                "assumption_table": assumption_table,
                "model_point_files": model_point_files,
                "projection_period": projection_period,
                "product_groups": product_groups
            }
            
            if save_button:
                save_settings(run_settings)
                st.success("Settings saved successfully!")
            
            if submitted:
                st.success("Settings validated! Ready to run pricing model.")
                
                # Run the pricing model
                with st.spinner('Running pricing model...'):
                    result = run_pricing_model(run_settings)
                    
                    if result['status'] == 'success':
                        st.success("Model run completed successfully!")
                        
                        # Display results
                        st.subheader("Model Results")
                        with st.expander(f"Results"):
                            st.write("Present Value:", result['results']['present_value'])
                            
                            st.write("Cashflows:")
                            st.dataframe(result['results']['cashflows'])

                    else:
                        st.error(result['message'])

if __name__ == "__main__":
    # Create uploads directory if it doesn't exist
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    main()