import streamlit as st
import datetime
from model_utils import load_assumptions, load_model_points, initialize_model, run_model_calculations
from settings_utils import load_settings, save_settings, validate_settings
from log import ModelLogger  # Import the ModelLogger class

# Initialize the logger
logger = ModelLogger()

def display_settings_management(saved_settings):
    """Display the settings management section"""
    with st.expander("Settings Management"):
        st.info("You can save your current settings or load previously saved settings.")
        if saved_settings and st.button("Load Saved Settings"):
            st.session_state.update(saved_settings)
            st.success("Settings loaded successfully!")

def collect_form_inputs(saved_settings):
    """Collect all form inputs and return settings dict"""
    default_date = datetime.date.today()
    if saved_settings and "valuation_date" in saved_settings:
        try:
            if isinstance(saved_settings["valuation_date"], str):
                default_date = datetime.datetime.strptime(
                    saved_settings["valuation_date"], "%Y-%m-%d"
                ).date()
            else:
                default_date = saved_settings["valuation_date"]
        except (ValueError, TypeError):
            pass
            
    settings = {
        "valuation_date": st.date_input(
            "Valuation Date",
            value=default_date,
            help="Select the valuation date for the pricing model"
        ),
        
        "assumption_table_url": st.text_input(
            "Enter S3 URL for assumption table",
            value=saved_settings.get("assumption_table_url", "") if saved_settings else "",
            help="Format: s3://bucket-name/path/to/file.xlsx"
        ),
        
        "model_point_files_url": st.text_input(
            "Enter S3 URL for model point files",
            value=saved_settings.get("model_point_files_url", "") if saved_settings else "",
            help="Format: s3://bucket-name/path/to/file.xlsx"
        ),
        
        "projection_period": st.number_input(
            "Projection Period (Years)",
            min_value=1,
            max_value=100,
            value=saved_settings.get("projection_period", 30) if saved_settings else 30,
            help="Enter the number of years to project"
        ),
        
        "product_groups": st.multiselect(
            "Select Product Groups to Run",
            options=[
                "Term Life", "Whole Life", "Universal Life",
                "Annuities", "Group Insurance", "Disability Insurance"
            ],
            default=saved_settings.get("product_groups", []) if saved_settings else [],
            help="Choose one or more product groups to include in the run"
        )
    }
    
    return settings

def process_model_run(settings):
    """Process the model run and display results"""
    start_time = datetime.datetime.now()
    try:
        # Download and process input files
        assumptions = load_assumptions(settings["assumption_table_url"])
        model_points_df = load_model_points(settings["model_point_files_url"])
        
        # Initialize and configure model
        model = initialize_model(settings, assumptions, model_points_df)
        
        # Run model for each product group
        results = run_model_calculations(model, settings["product_groups"])
        
        end_time = datetime.datetime.now()
        # Log successful run with ModelLogger
        logger.create_run_log(
            settings=settings,
            start_time=start_time,
            end_time=end_time,
            status="success",
            output_location=None  # You can add output location if needed
        )
        
        # Display results
        st.success("Model run completed successfully!")
        st.subheader("Model Results")
        for product, product_results in results.items():
            with st.expander(f"Results for {product}"):
                st.write("Present Value:", product_results['present_value'])
                st.write("Cashflows:")
                st.dataframe(product_results['cashflows'])
                st.write("Analytic:")
                st.write(product_results['analytic'])
                
    except Exception as e:
        end_time = datetime.datetime.now()
        # Log failed run with ModelLogger
        logger.create_run_log(
            settings=settings,
            start_time=start_time,
            end_time=end_time,
            status="error",
            error_message=str(e)
        )
        st.error(f"Error running model: {str(e)}")

def main():
    st.title("Enterprise Pricing Model Settings")
    
    saved_settings = load_settings()
    display_settings_management(saved_settings)
    # Add run history display
    logger.display_run_history(limit=10)

    with st.form("pricing_model_settings"):
        settings = collect_form_inputs(saved_settings)
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Run Pricing Model")
        with col2:
            save_button = st.form_submit_button("Save Settings")
        
        if submitted or save_button:
            try:
                validate_settings(settings)
                
                if save_button:
                    save_settings(settings)
                    st.success("Settings saved successfully!")
                
                if submitted:
                    process_model_run(settings)
                    
            except ValueError as e:
                st.error(str(e))

if __name__ == "__main__":
    main()


