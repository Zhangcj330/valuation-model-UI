import streamlit as st
import datetime
import os
import json
from pathlib import Path

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
                
            if not all([assumption_table, model_point_files, output_location]):
                st.error("Please fill in all file locations")
                return
                
            # Validate paths
            for path in [assumption_table, model_point_files, output_location]:
                if not os.path.exists(path):
                    st.error(f"Path does not exist: {path}")
                    return
            
            # Collect settings
            run_settings = {
                "valuation_date": val_date,
                "assumption_table": assumption_table,
                "model_point_files": model_point_files,
                "output_location": output_location,
                "projection_period": projection_period,
                "product_groups": product_groups
            }
            
            if save_button:
                save_settings(run_settings)
                st.success("Settings saved successfully!")
            
            if submitted:
                st.success("Settings validated! Ready to run pricing model.")
                st.json(run_settings)
                
                # TODO: Add your pricing model function call here
                # run_pricing_model(run_settings)

if __name__ == "__main__":
    # Create uploads directory if it doesn't exist
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    main()