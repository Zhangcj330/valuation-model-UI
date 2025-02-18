import streamlit as st
import datetime
import pandas as pd
import io
import msal
import requests
import app_config

from model_utils import load_assumptions, load_model_points, initialize_model
from settings_utils import load_settings, save_settings, validate_settings
from log import ModelLogger
from s3_utils import (
    get_excel_filenames_from_s3,
    upload_to_s3,
    get_foldernames_from_s3,
)

# Initialize the logger
logger = ModelLogger()

# Initialize session state for authentication
if "user" not in st.session_state:
    st.session_state.user = None
if "token" not in st.session_state:
    st.session_state.token = None

# Initialize MSAL application
msal_app = msal.ConfidentialClientApplication(
    app_config.CLIENT_ID,
    authority=app_config.AUTHORITY,
    client_credential=app_config.CLIENT_SECRET,
)


def get_auth_url() -> str:
    """Generate Microsoft login URL"""
    return msal_app.get_authorization_request_url(
        scopes=app_config.SCOPE,
        redirect_uri=app_config.REDIRECT_URI,
        state=st.session_state.get("state", ""),
        prompt="select_account",
    )


def authenticate_user():
    """Handle user authentication"""
    # Check for authentication code in URL parameters
    code = st.query_params.get("code")

    if code and not st.session_state.user:
        # Process authentication code
        result = msal_app.acquire_token_by_authorization_code(
            code=code, scopes=app_config.SCOPE, redirect_uri=app_config.REDIRECT_URI
        )
        if "error" in result:
            st.error(
                f"Authentication error: {result.get('error_description', 'Unknown error')}"
            )
            return False

        st.session_state.token = result
        # Get user info
        headers = {"Authorization": f'Bearer {result["access_token"]}'}
        response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if response.status_code == 200:
            st.session_state.user = response.json()
            st.query_params.clear()
            return True

    return bool(st.session_state.user)


def display_login():
    """Display login interface"""
    st.title("Enterprise Valuation Model")
    st.write("Please sign in with your Microsoft account to continue")
    login_url = get_auth_url()
    st.markdown(
        f"""
        <a href="{login_url}" target="_self">
            <button style="
                background-color: #2f7feb;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;">
                Sign in with Microsoft
            </button>
        </a>
        """,
        unsafe_allow_html=True,
    )


def display_settings_management(saved_settings):
    """Display the settings management section"""
    with st.expander("Settings Management"):
        st.info("You can save your current settings or load previously settings.")
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
            help="Select the valuation date for the valuation model",
        ),
        "assumption_table_url": st.text_input(
            "Enter S3 URL for assumption table",
            value=(
                saved_settings.get("assumption_table_url", "") if saved_settings else ""
            ),
            help="Format: s3://bucket-name/path/to/file.xlsx",
        ),
    }
    # Create a container for models URL and confirmation
    col1, col2 = st.columns([3, 1], gap="small", vertical_alignment="bottom")

    with col1:
        models_url = st.text_input(
            "Enter S3 URL for models",
            value=(saved_settings.get("models_url", "") if saved_settings else ""),
            help="Format: s3://bucket-name/path/",
            key="models_url_input",
        )
    with col2:
        confirm_button_models = st.form_submit_button("Check Models")

    settings["models_url"] = models_url

    # Handle URL confirmation and file listing
    if confirm_button_models and models_url:
        try:
            available_models = get_foldernames_from_s3(models_url)
            if available_models:
                st.session_state["available_models"] = available_models
            else:
                st.session_state["available_models"] = []
        except Exception as e:
            st.error(f"Error accessing S3 path: {str(e)}")
            st.session_state["available_models"] = []

    # Product Groups selection
    available_models = st.session_state.get("available_models", [])
    if available_models:
        selected_models = st.multiselect(
            "Model selection",
            options=available_models,
            default=(saved_settings.get("model_name", []) if saved_settings else []),
            help="Select model to process",
            placeholder="Please select your model",
        )
    else:
        st.selectbox(
            "Model selection",
            options=available_models,
            help="Confirm model points files URL to show the available models",
        )
        selected_models = []

    settings["model_name"] = selected_models

    # Create a container for model point URL and confirmation
    col1, col2 = st.columns([3, 1], gap="small", vertical_alignment="bottom")

    with col1:
        model_point_url = st.text_input(
            "Enter S3 URL for model point files",
            value=(
                saved_settings.get("model_point_files_url", "")
                if saved_settings
                else ""
            ),
            help="Format: s3://bucket-name/path/",
            key="mp_url_input",
        )
    with col2:
        confirm_button = st.form_submit_button("Confirm URL")

    settings["model_point_files_url"] = model_point_url

    # Handle URL confirmation and file listing
    if confirm_button and model_point_url:
        try:
            available_products = get_excel_filenames_from_s3(model_point_url)
            if available_products:
                st.session_state["available_products"] = available_products
            else:
                st.session_state["available_products"] = []
        except Exception as e:
            st.error(f"Error accessing S3 path: {str(e)}")
            st.session_state["available_products"] = []

    # Product Groups selection
    available_products = st.session_state.get("available_products", [])
    if available_products:
        # Filter default values to ensure they exist in available options
        default_products = []
        if saved_settings and "product_groups" in saved_settings:
            default_products = [
                p for p in saved_settings["product_groups"] if p in available_products
            ]

        selected_products = st.multiselect(
            "Product Groups",
            options=available_products,
            default=default_products,  # Use filtered defaults
            help="Select product groups to process",
            placeholder="Please select at least one product group",
        )
    else:
        st.multiselect(
            "Product Groups",
            options=available_products,
            help="Confirm model points files URL to show the available products",
        )
        selected_products = []

    settings["product_groups"] = selected_products

    settings["projection_period"] = st.number_input(
        "Projection Period (Years)",
        min_value=1,
        max_value=100,
        value=(saved_settings.get("projection_period", 30) if saved_settings else 30),
        help="Enter the number of years to project",
    )

    settings["output_s3_url"] = st.text_input(
        "Enter S3 URL for storing results",
        value=(saved_settings.get("output_s3_url", "") if saved_settings else ""),
        help="Format: s3://bucket-name/path/to/output/folder/",
    )

    return settings


def initialize_progress_indicators():
    """Initialize and return progress tracking components"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    time_text = st.empty()
    return progress_bar, status_text, time_text


def clear_progress_indicators(progress_bar, status_text, time_text):
    """Clear all progress tracking components"""
    progress_bar.empty()
    status_text.empty()
    time_text.empty()


def run_single_model(product, settings, model_points_list, assumptions):
    """Run model for a single product and return results"""
    # Find matching model points file for this product
    model_points_df = model_points_list[product]

    # Initialize and run model
    model = initialize_model(settings, assumptions, model_points_df)

    # Generate results
    pv_df = model.Results.pv_results(0)
    analytics_df = model.Results.analytics()

    return {
        "present_value": pv_df,
        "analytics": analytics_df,
        "model_points_count": len(model_points_df),
        "results_count": len(pv_df),
    }


def process_model_results(product, model_results, settings, start_time):
    """Process and save model results for a single product"""
    # Prepare Excel output
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
        model_results["analytics"].to_excel(writer, sheet_name="analytics", index=False)
        model_results["present_value"].to_excel(
            writer, sheet_name="present_value", index=False
        )

    # Save to S3
    output_filename = f"results_{product}_{start_time}.xlsx"
    output_path = f"{settings['output_s3_url'].rstrip('/')}/{output_filename}"
    output_buffer.seek(0)
    upload_to_s3(output_buffer.getvalue(), output_path)

    return {"output_path": output_path, "results": model_results}


def process_single_product(
    product,
    product_idx,
    settings,
    model_points_list,
    assumptions,
    total_products,
    progress_bar,
    current_step,
    total_steps,
    start_time,
):
    """Process a single product and return its results"""
    status_text = st.empty()
    status_text.text(f"Processing {product}... ({product_idx}/{total_products})")

    # Run model
    model_results = run_single_model(product, settings, model_points_list, assumptions)
    current_step += 1
    progress_bar.progress(current_step / total_steps)

    # Process and save results
    processed_results = process_model_results(
        product, model_results, settings, start_time
    )

    return processed_results, current_step


def display_results(results, output_locations, total_time):
    """Display the results of the model run"""
    st.success(f"Model run completed successfully in {total_time:.1f} seconds!")
    st.write("Results saved to:")
    for location in output_locations:
        st.write(f"- {location}")

    # Display results in a simpler format
    st.subheader("Model Results")
    for product, product_results in results.items():
        with st.expander(f"Results for {product}"):
            # Display record count comparison
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="Model Points Count",
                    value=product_results["model_points_count"],
                )
            with col2:
                st.metric(
                    label="Results Count",
                    value=product_results["results_count"],
                )

            if (
                product_results["model_points_count"]
                != product_results["results_count"]
            ):
                st.warning("⚠️ Number of results doesn't match number of model points!")
            else:
                st.success("✅ Number of results matches number of model points")

            st.write("Present Value:")
            st.write(product_results["present_value"])
            st.write("Analytics:")
            st.write(product_results["analytics"])


def process_model_run(settings):
    """Process the model run and display results"""
    st.success("Settings validated! Ready to run valuation model.")

    # Initialize progress tracking
    progress_bar, status_text, time_text = initialize_progress_indicators()
    start_time = datetime.datetime.now()

    with st.spinner("Running valuation model..."):
        try:
            # Download and process input files
            status_text.text("Downloading and processing input files...")
            assumptions = load_assumptions(settings["assumption_table_url"])
            model_points_list = load_model_points(settings["model_point_files_url"])

            # Initialize tracking variables
            total_steps = len(settings["product_groups"]) * 2  # 2 steps per product
            current_step = 0
            progress_bar.progress(current_step / total_steps)
            output_locations = []
            results = {}

            # Process each product
            for product_idx, product in enumerate(settings["product_groups"], 1):
                product_result, current_step = process_single_product(
                    product=product,
                    product_idx=product_idx,
                    settings=settings,
                    model_points_list=model_points_list,
                    assumptions=assumptions,
                    total_products=len(settings["product_groups"]),
                    progress_bar=progress_bar,
                    current_step=current_step,
                    total_steps=total_steps,
                    start_time=start_time,
                )

                output_locations.append(product_result["output_path"])
                results[product] = product_result["results"]
                current_step += 1
                progress_bar.progress(current_step / total_steps)

            # Calculate total time
            end_time = datetime.datetime.now()
            total_time = (end_time - start_time).total_seconds()

            # Log successful run
            logger.create_run_log(
                settings=settings,
                start_time=start_time,
                end_time=end_time,
                status="success",
                output_location=output_locations,
            )

            # Clear progress indicators and display results
            clear_progress_indicators(progress_bar, status_text, time_text)
            display_results(results, output_locations, total_time)

        except Exception as e:
            # Clear progress indicators
            clear_progress_indicators(progress_bar, status_text, time_text)

            end_time = datetime.datetime.now()
            # Log failed run
            logger.create_run_log(
                settings=settings,
                start_time=start_time,
                end_time=end_time,
                status="error",
                error_message=str(e),
            )
            st.error(f"Error running model: {str(e)}")


def main():
    """Main application function"""
    # Check authentication
    if not authenticate_user():
        display_login()
        return

    # Display user info in sidebar
    with st.sidebar:
        user = st.session_state.user
        st.write(f"Welcome, {user.get('displayName', 'User')}!")
        if st.button("Logout"):
            st.session_state.user = None
            st.session_state.token = None
            st.rerun()

    # Original app content
    st.title("Enterprise Valuation Model Settings")

    saved_settings = load_settings()
    display_settings_management(saved_settings)

    if "history_page" not in st.session_state:
        st.session_state["history_page"] = 1
    logger.display_run_history(page=st.session_state["history_page"])

    with st.form("valuation_model_settings"):
        settings = collect_form_inputs(saved_settings)

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Run valuation Model")
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
