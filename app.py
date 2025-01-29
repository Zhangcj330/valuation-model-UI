import streamlit as st
import datetime
import pandas as pd

from model_utils import load_assumptions, load_model_points, initialize_model, run_model_calculations, save_results_to_s3, process_all_model_points
from settings_utils import load_settings, save_settings, validate_settings
from log import ModelLogger 
from s3_utils import get_excel_filenames_from_s3

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
    }
    
    # Create a container for model point URL and confirmation
    col1, col2 = st.columns([3, 1], gap="small" , vertical_alignment="bottom")
    
    with col1:
        model_point_url = st.text_input(
            "Enter S3 URL for model point files",
            value=saved_settings.get("model_point_files_url", "") if saved_settings else "",
            help="Format: s3://bucket-name/path/",
            key="mp_url_input"
        )
    with col2:
        confirm_button = st.form_submit_button("Confirm URL")
    
    settings["model_point_files_url"] = model_point_url
    
    # Handle URL confirmation and file listing
    if confirm_button and model_point_url:
        try:
            available_products = get_excel_filenames_from_s3(model_point_url)
            if available_products:
                st.session_state['available_products'] = available_products
            else:
                st.session_state['available_products'] = []
        except Exception as e:
            st.error(f"Error accessing S3 path: {str(e)}")
            st.session_state['available_products'] = []
    
    settings["projection_period"] = st.number_input(
        "Projection Period (Years)",
        min_value=1,
        max_value=100,
        value=saved_settings.get("projection_period", 30) if saved_settings else 30,
        help="Enter the number of years to project"
    )
    
    # Product Groups selection
    available_products = st.session_state.get('available_products', [])
    if available_products:
        selected_products = st.multiselect(
            "Product Groups",
            options=available_products,
            default=saved_settings.get("product_groups", []) if saved_settings else [],
            help="Select product groups to process",
            placeholder="Please select at least one product group"
        )
    else:
        st.multiselect("Product Groups" , options=available_products, help="Confirm model points files URL to show the available products")
        selected_products = []
    
    settings["product_groups"] = selected_products
    
    settings["output_s3_url"] = st.text_input(
        "Enter S3 URL for storing results",
        value=saved_settings.get("output_s3_url", "") if saved_settings else "",
        help="Format: s3://bucket-name/path/to/output/folder/"
    )
    
    return settings

def process_model_run(settings):
    """Process the model run and display results"""
    st.success("Settings validated! Ready to run pricing model.")
    
    # Initialize progress indicators
    progress_bar = st.progress(0)
    status_text = st.empty()
    time_text = st.empty()
    
    start_time = datetime.datetime.now()
    
    with st.spinner('Running pricing model...'):
        try:
            # Download and process input files
            status_text.text("Downloading and processing input files...")
            assumptions = load_assumptions(settings["assumption_table_url"])
            model_points_list = load_model_points(settings["model_point_files_url"])
            
            # Calculate total steps (3 steps per product per model point file)
            steps_per_product = 3
            total_steps = len(settings["product_groups"]) * steps_per_product * len(model_points_list)
            current_step = 0
            progress_bar.progress(current_step / total_steps)
            
            all_results = {}
            
            # Process each model point file
            for mp_idx, model_points_df in enumerate(model_points_list, 1):
                status_text.text(f"Processing model point file {mp_idx}/{len(model_points_list)}...")
                product_groups = settings["product_groups"][mp_idx-1]
                # Initialize model for this set of model points
                model = initialize_model(settings, assumptions, model_points_df)
                current_step += 1
                progress_bar.progress(current_step / total_steps)
                
                results = {}
                # Run model for each product group
                for product_idx, product in enumerate(settings["product_groups"], 1):
                    current_time = datetime.datetime.now()
                    elapsed_time = (current_time - start_time).total_seconds()
                    
                    # Calculate average time per step and estimated remaining time
                    avg_time_per_step = elapsed_time / current_step if current_step > 0 else 0
                    remaining_steps = total_steps - current_step
                    estimated_remaining_time = avg_time_per_step * remaining_steps
                    
                    status_text.text(f"Processing {product} for model point set {mp_idx}... "
                                   f"({product_idx}/{len(settings['product_groups'])})")
                    time_text.text(f"Estimated time remaining: {estimated_remaining_time:.1f} seconds")
                    
                    # Calculate results for current product
                    results[product] = {
                        'present_value': model.Results_at_t.aggregate_pvs(),
                        'cashflows': model.Results_at_t.aggregate_cfs().to_dict(),
                        'analytic': model.Results_at_t.analytic() 
                    }
                    current_step += 2  # Increment for initialization and calculation
                    progress_bar.progress(current_step / total_steps)
                
                # Generate unique identifier for this model point set
                all_results[product_groups] = results
            
            # Save results to S3
            status_text.text("Saving results to S3...")
            output_locations = save_results_to_s3(
                all_results, 
                settings["model_point_files_url"],
                settings["output_s3_url"]
            )
            
            end_time = datetime.datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            # Log successful run
            logger.create_run_log(
                settings=settings,
                start_time=start_time,
                end_time=end_time,
                status="success",
                output_location=output_locations
            )
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            time_text.empty()
            
            # Display results
            st.success(f"Model run completed successfully in {total_time:.1f} seconds!")
            st.write("Results saved to:")
            for location in output_locations:
                st.write(f"- {location}")
                
            st.subheader("Model Results")
            for product, results in all_results.items():
                with st.expander(f"Results for Model Point Set: {product}"):
                    for product, product_results in results.items():
                        st.write(f"\nProduct: {product}")
                        st.write("Present Value:", product_results['present_value'])
                        st.write("Cashflows:")
                        st.dataframe(pd.DataFrame(product_results['cashflows']))
                        st.write("Analytic:")
                        st.write(product_results['analytic'])
                    
        except Exception as e:
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            time_text.empty()
            
            end_time = datetime.datetime.now()
            # Log failed run
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
                if submitted:
                    # Full validation when running the model
                    validate_settings(settings, validate_required=True)
                    process_model_run(settings)
                else:
                    save_settings(settings)
                    st.success("Settings saved successfully!")
                    
            except ValueError as e:
                st.error(str(e))

if __name__ == "__main__":
    main()


