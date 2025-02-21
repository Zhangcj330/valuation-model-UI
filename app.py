import streamlit as st
import datetime
import pandas as pd
import io
import msal
import requests
import app_config

from model_utils import initialize_model, get_model_handler
from settings_utils import load_settings, save_settings, validate_settings
from log import ModelLogger
from s3_utils import S3Client
from sharepoint_utils import SharePointClient

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
    st.info("You can save your current settings or load previously saved settings.")

    storage_type = st.session_state.get("storage_type", "SharePoint")
    settings = {}

    # Preserve all settings regardless of storage type
    if saved_settings:
        settings = saved_settings.copy()

    # Define common field names and their display labels
    field_configs = {
        "assumption_url": {
            "label": "Assumptions Path",
            "help": {
                "S3": "Format: s3://bucket-name/path/to/file.xlsx",
                "SharePoint": "Enter the relative path to the assumptions folder",
            },
        },
        "models_url": {
            "label": "Models Path",
            "help": {
                "S3": "Format: s3://bucket-name/path/",
                "SharePoint": "Enter the relative path to the models folder",
            },
        },
        "model_points_url": {
            "label": "Model Points Path",
            "help": {
                "S3": "Format: s3://bucket-name/path/",
                "SharePoint": "Enter the relative path to the model points folder",
            },
        },
        "results_url": {
            "label": "Results Path",
            "help": {
                "S3": "Format: s3://bucket-name/path/to/output/folder/",
                "SharePoint": "Enter the relative path to store results",
            },
        },
    }

    prefix = "s3_" if storage_type == "S3" else "sp_"

    # Create input fields dynamically
    for base_key, config in field_configs.items():
        prefixed_key = f"{prefix}{base_key}"
        settings[prefixed_key] = st.text_input(
            config["label"],
            value=saved_settings.get(prefixed_key, ""),
            help=config["help"][storage_type],
            key=f"{prefixed_key}_input",
        )
        # Map to generic keys for the rest of the application
        settings[base_key] = settings[prefixed_key]

    # Form buttons
    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        load_button = st.button("Load Settings")
    with col3:
        save_button = st.button("Save Settings")

    if load_button:
        st.success("Settings loaded successfully!")
        st.rerun()
    if save_button:
        save_settings(settings)
        st.success("Settings saved successfully!")
    return settings


def collect_S3_inputs(saved_settings):
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
        )
    }

    # Use the generic URL keys that were mapped in display_settings_management
    models_url = saved_settings.get("models_url", "")
    if models_url:
        try:
            available_models = S3Client().list_folders(models_url)
            if available_models:
                st.session_state["available_models"] = available_models
            else:
                st.session_state["available_models"] = []
        except Exception as e:
            st.error(f"Error accessing S3 path: {str(e)}")
            st.session_state["available_models"] = []
    else:
        st.session_state["available_models"] = []

    # Model Point Files selection
    available_models = st.session_state.get("available_models", [])
    selected_models = st.selectbox(
        "Model selection",
        options=available_models,
        help="Select model to process",
        placeholder="Please select your model"
        if available_models
        else "No models available",
    )

    settings["model_name"] = selected_models

    model_points_url = saved_settings.get("model_points_url", "")
    if model_points_url:
        try:
            available_products = S3Client().list_files(model_points_url)
            if available_products:
                st.session_state["available_products"] = available_products
            else:
                st.session_state["available_products"] = []
        except Exception as e:
            st.error(f"Error accessing S3 path: {str(e)}")
            st.session_state["available_products"] = []
    else:
        st.session_state["available_products"] = []

    # Model Point Files selection
    available_products = st.session_state.get("available_products", [])
    default_products = []
    if saved_settings and "product_groups" in saved_settings:
        default_products = [
            p for p in saved_settings["product_groups"] if p in available_products
        ]

    selected_products = st.multiselect(
        "Model Point Files",
        options=available_products,
        default=default_products,
        help="Select model point files to process",
        placeholder="Please select at least one model point file"
        if available_products
        else "No model point files available",
    )

    settings["product_groups"] = selected_products

    settings["projection_period"] = st.number_input(
        "Projection Period (Years)",
        min_value=1,
        max_value=100,
        value=(saved_settings.get("projection_period", 30) if saved_settings else 30),
        help="Enter the number of years to project",
    )

    # Copy over the URLs from saved settings
    for key in ["assumption_url", "models_url", "model_points_url", "results_url"]:
        settings[key] = saved_settings.get(key, "")

    return settings


def collect_sharepoint_inputs(saved_settings) -> dict:
    """Collect all form inputs for SharePoint storage"""
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
        )
    }

    # Use the generic URL keys that were mapped in display_settings_management
    models_url = saved_settings.get("models_url", "")
    if models_url:
        try:
            # Here you would implement SharePoint folder listing
            available_models = SharePointClient().list_folders(models_url)
            if available_models:
                st.session_state["available_models"] = available_models
            else:
                st.session_state["available_models"] = []
        except Exception as e:
            st.error(f"Error accessing SharePoint: {str(e)}")
            st.session_state["available_models"] = []
    else:
        st.session_state["available_models"] = []

    # Model selection
    available_models = st.session_state.get("available_models", [])
    selected_models = st.selectbox(
        "Model selection",
        options=available_models,
        help="Select model to process",
        placeholder="Please select your model"
        if available_models
        else "No models available",
    )

    settings["model_name"] = selected_models

    model_points_url = saved_settings.get("model_points_url", "")
    if model_points_url:
        try:
            # Here you would implement SharePoint file listing
            available_products = SharePointClient().list_files(
                model_points_url
            )  # get_sharepoint_excel_files(model_points_url)
            if available_products:
                st.session_state["available_products"] = available_products
            else:
                st.session_state["available_products"] = []
        except Exception as e:
            st.error(f"Error accessing SharePoint: {str(e)}")
            st.session_state["available_products"] = []
    else:
        st.session_state["available_products"] = []

    # Model Point Files selection
    available_products = st.session_state.get("available_products", [])
    default_products = []
    if saved_settings and "product_groups" in saved_settings:
        default_products = [
            p for p in saved_settings["product_groups"] if p in available_products
        ]

    selected_products = st.multiselect(
        "Model Point Files",
        options=available_products,
        default=default_products,
        help="Select model point files to process",
        placeholder="Please select at least one model point file"
        if available_products
        else "No model point files available",
    )

    settings["product_groups"] = selected_products

    settings["projection_period"] = st.number_input(
        "Projection Period (Years)",
        min_value=1,
        max_value=100,
        value=(saved_settings.get("projection_period", 30) if saved_settings else 30),
        help="Enter the number of years to project",
    )

    # Copy over the URLs from saved settings
    for key in ["assumption_url", "models_url", "model_points_url", "results_url"]:
        settings[key] = saved_settings.get(key, "")

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


def process_single_model_point(
    product,
    product_idx,
    settings,
    model_points_df,
    assumptions,
    total_products,
    progress_bar,
    current_step,
    total_steps,
):
    """Process a single product and return its results"""
    status_text = st.empty()
    status_text.text(f"Processing {product}... ({product_idx}/{total_products})")

    # Run model
    proj_period = settings["projection_period"]
    val_date = settings["valuation_date"]
    model = initialize_model(assumptions, model_points_df, proj_period, val_date)

    current_step += 1
    progress_bar.progress(current_step / total_steps)

    # Process and save results
    pv_df = model.Results.pv_results(0)
    analytics_df = model.Results.analytics()

    model.close()

    model_results = {
        "present_value": pv_df,
        "analytics": analytics_df,
        "model_points_count": len(model_points_df),
        "results_count": len(pv_df),
    }
    status_text.empty()

    return model_results, current_step


def format_results(model_results):
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
        model_results["analytics"].to_excel(writer, sheet_name="analytics", index=False)
        model_results["present_value"].to_excel(
            writer, sheet_name="present_value", index=False
        )
    return output_buffer


def display_results(results):
    """Display the results of the model run"""

    # Display results in a simpler format
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

    # Initialize progress tracking
    progress_bar, status_text, time_text = initialize_progress_indicators()
    start_time = datetime.datetime.now()
    output_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with st.spinner("Running valuation model..."):
        try:
            # Get appropriate model handler
            handler = get_model_handler(
                st.session_state.get("storage_type", "SharePoint")
            )
            # Download and process input files
            status_text.text("Downloading and processing input files...")
            assumptions = handler.download_assumptions(settings["assumption_url"])
            handler.download_model(
                settings.get("models_url"), settings.get("model_name")
            )
            model_points_list = handler.download_model_points(
                settings["model_points_url"], settings["product_groups"]
            )
            print("download success")
            # Initialize tracking variables
            total_steps = len(settings["product_groups"]) * 2  # 2 steps per product
            current_step = 0
            progress_bar.progress(current_step / total_steps)

            results = {}

            # Process each product
            for product_idx, product in enumerate(settings["product_groups"], 1):
                model_result, current_step = process_single_model_point(
                    product=product,
                    product_idx=product_idx,
                    settings=settings,
                    model_points_df=model_points_list[product],
                    assumptions=assumptions,
                    total_products=len(settings["product_groups"]),
                    progress_bar=progress_bar,
                    current_step=current_step,
                    total_steps=total_steps,
                )

                current_step += 1
                progress_bar.progress(current_step / total_steps)

                output_buffer = format_results(model_result)
                output_filename = f"results_{product}_{output_timestamp}.xlsx"
                output_path = f"{settings['results_url'].rstrip('/')}/{output_filename}"
                handler.save_results(output_buffer.getvalue(), output_path)
                results[product] = model_result

            # Calculate total time
            end_time = datetime.datetime.now()
            total_time = (end_time - start_time).total_seconds()

            # Log successful run
            logger.create_run_log(
                settings=settings,
                start_time=start_time,
                end_time=end_time,
                status="success",
                output_location=settings["results_url"],
            )

            # Clear progress indicators and display results
            clear_progress_indicators(progress_bar, status_text, time_text)

            st.session_state["results"] = results
            st.success(f"Model run completed successfully in {total_time:.1f} seconds!")
            if st.session_state.get("storage_type") == "SharePoint":
                output_file_url = handler.get_file_url(settings["results_url"])
                st.write("Results saved to URL: %s" % output_file_url)
            else:
                st.write("Results saved to: %s" % settings["results_url"])

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


def convert_date_string(date_str):
    """Convert a date string to a datetime.date object"""
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        st.error(f"Invalid date format: {date_str}")
        return None


def convert_to_list(value):
    """Convert a comma-separated string to a list"""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",")]
    return value


def process_batch_run(configurations):
    """Process each configuration in the batch run"""
    for config in configurations:
        st.write(f"Running configuration: {config['run_number']}")
        try:
            # Convert date strings to date objects
            if isinstance(config.get("valuation_date"), str):
                config["valuation_date"] = convert_date_string(config["valuation_date"])
            # Convert product_groups to a list if it's a string
            config["product_groups"] = convert_to_list(config.get("product_groups", []))
            config["projection_period"] = int(config["projection_period"])
            # Validate settings
            validate_settings(config, validate_required=True)
            validation_text = st.empty()
            validation_text.success("Settings validated! Ready to run valuation model.")
            print(config)
            process_model_run(config)
            validation_text.empty()
            if "results" not in st.session_state:
                st.info("Run model to display the results")
            else:
                display_results(st.session_state["results"])
            st.success(f"Run {config['run_number']} completed successfully!")
        except Exception as e:
            st.error(f"Error in run {config['run_number']}: {str(e)}")


def main():
    """Main application function"""
    # Check authentication
    if not authenticate_user():
        display_login()
        return

    with st.sidebar:
        user = st.session_state.user
        st.write(f"Welcome, {user.get('displayName', 'User')}!")
        if st.button("Logout", key="logout_button"):
            st.session_state.user = None
            st.session_state.token = None
            st.rerun()

    st.title("Enterprise Valuation Model")

    # Create main tabs
    singlerun, batchrun, history_tab = st.tabs(
        ["Single Run", "Batch Run", "Run History"]
    )

    # Single Run tab
    with singlerun:
        # Settings management
        saved_settings = load_settings()
        with st.expander("Settings Management"):
            # Storage configuration section
            storage_type = st.radio(
                "Select Storage Type", options=["SharePoint", "S3"], horizontal=True
            )
            # File selection based on storage type
            st.session_state["storage_type"] = storage_type
            url_settings = display_settings_management(saved_settings)

        # Create main form for inputs
        if storage_type == "S3":
            settings = collect_S3_inputs(url_settings)
        else:
            settings = collect_sharepoint_inputs(saved_settings)

        # Form buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submitted = st.button("Run Model")

        # Handle form submission
        if submitted:
            validate_settings(settings, validate_required=True)
            validation_text = st.empty()
            validation_text.success("Settings validated! Ready to run valuation model.")
            process_model_run(settings)
            validation_text.empty()
            st.subheader("Model Results")
            if "results" not in st.session_state:
                st.info("Run model to display the results")
            else:
                display_results(st.session_state["results"])

    # Batch Run tab
    with batchrun:
        st.subheader("Batch Run Configuration")
        uploaded_file = st.file_uploader("Upload Configuration File", type=["xlsx"])

        if uploaded_file is not None:
            try:
                # Read the Excel file
                df = pd.read_excel(uploaded_file)
                configurations = df.to_dict(orient="records")
                st.write("Configuration loaded successfully!")
                st.dataframe(df)  # Display the configurations for confirmation

                if st.button("Run Batch"):
                    st.subheader("Model Results")
                    process_batch_run(configurations)
                    st.write("Preview of the input configurations:")

            except Exception as e:
                st.error(f"Error loading configuration file: {str(e)}")

    # Run History tab
    with history_tab:
        st.subheader("Model Run History")
        if "history_page" not in st.session_state:
            st.session_state["history_page"] = 1
        logger.display_run_history(page=st.session_state["history_page"])


if __name__ == "__main__":
    main()
