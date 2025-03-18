import streamlit as st
import datetime
import pandas as pd
import io
import msal
import requests
import app_config

from model_utils import initialize_model_IP, initialize_model_LS, get_model_handler
from settings_utils import load_config, save_config, ModelSettings
from log import ModelLogger
from s3_utils import S3Client
from sharepoint_utils import SharePointClient
from mpf_validation import validate_mpf_dataframe

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


def callback():
    st.session_state.run_botton_clicked = True


def callback_stop():
    st.session_state.run_botton_clicked = False


def callback_batch():
    st.session_state.batch_run_button_clicked = True


@st.cache_data(ttl=3600, show_spinner=False)  # 1小时后缓存失效
def cached_download_model(models_url: str, model_name: str):
    handler = get_model_handler(st.session_state.get("storage_type", "SharePoint"))
    return handler.download_model(models_url, model_name)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_download_assumptions_IP(assumption_url: str):
    handler = get_model_handler(st.session_state.get("storage_type", "SharePoint"))
    return handler.download_assumptions_IP(assumption_url)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_download_model_points(model_points_url: str, product_groups: list):
    handler = get_model_handler(st.session_state.get("storage_type", "SharePoint"))
    return handler.download_model_points(model_points_url, product_groups)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_download_assumptions_LS(assumption_url: str):
    handler = get_model_handler(st.session_state.get("storage_type", "SharePoint"))
    return handler.download_assumptions_LS(assumption_url)


def display_settings_management(saved_settings):
    """Display the settings management section"""
    st.info("You can save your current settings.")

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
                "S3": "Format: s3://bucket-name/path/to/assumptions/folder/",
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
        # Load the saved configuration
        st.success("Settings loaded successfully!")
        st.rerun()
    if save_button:
        save_config(settings)
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


def validate_all_mpf(settings_dict):
    """Process the model run and display results"""
    # Convert settings dictionary to ModelSettings object
    settings = ModelSettings.from_dict(settings_dict)

    # Initialize validation state if not already present
    if "validation_state" not in st.session_state:
        st.session_state.validation_state = {}

    with st.spinner("Running mpf validation..."):
        try:
            # Download and process input files
            print("downloading ..........")

            model_points_list = cached_download_model_points(
                settings.model_points_url, settings.product_groups
            )
            print("Finished downloading")
            df_rules = pd.read_excel(
                "MPF_Data_Validation_Check_Sample.xlsx", sheet_name="Rules_Input"
            )

            # Track if all products are validated
            all_validated = True

            for product_idx, product in enumerate(settings.product_groups, 1):
                # Initialize product validation state if not present
                if product not in st.session_state.validation_state:
                    st.session_state.validation_state[product] = {"validated": False}

                # Skip if already validated
                if st.session_state.validation_state[product]["validated"]:
                    continue

                current_mpf_data = model_points_list.get(product)

                # 根据模型类型选择验证方式
                model_type = "IP" if "IP" in settings.model_name else "LS"

                validation_results, cleaned_df, invalid_rows = validate_mpf_dataframe(
                    current_mpf_data, df_rules, str(settings.valuation_date), model_type
                )

                # 显示整体状态
                if invalid_rows.empty:
                    st.success(f"✅ All validation checks passed for {product}!")
                    st.session_state.validation_state[product] = {
                        "validated": True,
                        "mpf_data": cleaned_df,
                    }
                else:
                    all_validated = False
                    # Display failed checks only
                    for check_name, result in validation_results.items():
                        if check_name != "column_checks":
                            if result["status"] != "Success":
                                st.error(f"⚠️ {result['message']}")

                    # Display failed column-specific checks only
                    if "column_checks" in validation_results:
                        failed_cols = [
                            col
                            for col, res in validation_results["column_checks"].items()
                            if res["status"] != "Success"
                        ]
                        if failed_cols:
                            st.subheader(f"Failed column validations for {product}:")
                            for col_name in failed_cols:
                                col_result = validation_results["column_checks"][
                                    col_name
                                ]
                                st.error(f"⚠️ {col_result['message']}")

                    # If there are invalid rows, show them and ask user what to do
                    with st.expander(
                        f"Found {len(invalid_rows)} invalid rows in {product} MPF data.",
                        expanded=True,
                    ):
                        st.dataframe(invalid_rows)

                        # Option to download invalid rows
                        invalid_buffer = io.BytesIO()
                        with pd.ExcelWriter(
                            invalid_buffer, engine="openpyxl"
                        ) as writer:
                            invalid_rows.to_excel(
                                writer, index=False, sheet_name="Invalid_Rows"
                            )

                        st.download_button(
                            label="📥 Download Invalid Rows",
                            data=invalid_buffer.getvalue(),
                            file_name=f"invalid_mpf_rows_{product}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"download_invalid_rows_{product}",
                        )

                    # Create three buttons for user action
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if st.button(
                            "Stop and fix the data", key=f"stop_button_{product}"
                        ):
                            st.session_state.validation_state = {}
                            st.session_state.run_botton_clicked = False
                            st.rerun()

                    with col2:
                        if st.button(
                            "Continue with cleaned data",
                            key=f"filter_button_{product}",
                        ):
                            st.warning(
                                f"Proceeding with {len(cleaned_df)} valid rows. {len(invalid_rows)} rows will be excluded."
                            )
                            st.session_state.validation_state[product] = {
                                "validated": True,
                                "mpf_data": cleaned_df,
                            }
                            st.rerun()

                    with col3:
                        if st.button(
                            "Continue with original data",
                            key=f"continue_button_{product}",
                        ):
                            st.warning(
                                "Proceeding with original data including invalid rows."
                            )
                            st.session_state.validation_state[product] = {
                                "validated": True,
                                "mpf_data": current_mpf_data,
                            }
                            st.rerun()

            # Return validation status
            return all_validated

        except Exception as e:
            st.error(f"Error during MPF validation: {str(e)}")
            logger.warning(f"MPF Validation error: {str(e)}", exc_info=True)
            st.session_state.validation_state = {}
            return False


def validate_batch_mpf(config, run_number):
    """Validate model point files for a specific batch run configuration"""
    # 确保 product_groups 是列表形式
    if isinstance(config.get("product_groups"), str):
        # 如果是逗号分隔的字符串，转换为列表
        config["product_groups"] = [
            p.strip() for p in config["product_groups"].split(",")
        ]
    elif not isinstance(config.get("product_groups"), list):
        # 如果既不是字符串也不是列表，则确保它是可迭代的并转换为列表
        try:
            config["product_groups"] = list(config["product_groups"])
        except TypeError:
            st.error(
                f"Invalid product_groups format in run #{run_number}. Expected a list or a comma-separated string."
            )
            return False
        except ValueError:
            st.error(
                f"Invalid product_groups data in run #{run_number}. Could not convert to list."
            )
            return False
    # Convert settings dictionary to ModelSettings object
    settings = ModelSettings.from_dict(config)

    settings.run_number = run_number
    # Initialize batch validation state for this run if not already present
    if run_number not in st.session_state.batch_validation_state:
        st.session_state.batch_validation_state[run_number] = {}

    with st.spinner(f"Running validation for configuration #{run_number}..."):
        try:
            # Download and process input files
            model_points_list = cached_download_model_points(
                settings.model_points_url, settings.product_groups
            )

            df_rules = pd.read_excel(
                "MPF_Data_Validation_Check_Sample.xlsx", sheet_name="Rules_Input"
            )
            # Track if all products in this run are validated
            all_validated = True

            for product_idx, product in enumerate(settings.product_groups, 1):
                # Initialize product validation state if not present
                if product not in st.session_state.batch_validation_state[run_number]:
                    st.session_state.batch_validation_state[run_number][product] = {
                        "validated": False
                    }
                # Skip if already validated
                if st.session_state.batch_validation_state[run_number][product][
                    "validated"
                ]:
                    continue

                current_mpf_data = model_points_list.get(product)
                # Determine model type based on model name
                model_type = "IP" if "IP" in settings.model_name else "LS"
                validation_results, cleaned_df, invalid_rows = validate_mpf_dataframe(
                    current_mpf_data, df_rules, str(settings.valuation_date), model_type
                )

                # Check validation results
                if invalid_rows.empty:
                    st.success(
                        f"✅ All validation checks passed for {product} in run #{run_number}!"
                    )
                    st.session_state.batch_validation_state[run_number][product] = {
                        "validated": True,
                        "mpf_data": cleaned_df,
                    }
                else:
                    all_validated = False

                    # Use a container instead of an expander to avoid nesting issues
                    st.markdown(
                        f"### Run #{run_number} - {product} - Found {len(invalid_rows)} invalid rows"
                    )

                    # Display failed checks only
                    for check_name, result in validation_results.items():
                        if check_name != "column_checks":
                            if result["status"] != "Success":
                                st.error(f"⚠️ {result['message']}")

                    # Display failed column-specific checks only
                    if "column_checks" in validation_results:
                        failed_cols = [
                            col
                            for col, res in validation_results["column_checks"].items()
                            if res["status"] != "Success"
                        ]
                        if failed_cols:
                            st.subheader("Failed column validations:")
                            for col_name in failed_cols:
                                col_result = validation_results["column_checks"][
                                    col_name
                                ]
                                st.error(f"⚠️ {col_result['message']}")

                    # Show invalid rows
                    st.dataframe(invalid_rows)

                    # Option to download invalid rows
                    invalid_buffer = io.BytesIO()
                    with pd.ExcelWriter(invalid_buffer, engine="openpyxl") as writer:
                        invalid_rows.to_excel(
                            writer, index=False, sheet_name="Invalid_Rows"
                        )

                    st.download_button(
                        label="📥 Download Invalid Rows",
                        data=invalid_buffer.getvalue(),
                        file_name=f"invalid_mpf_rows_run{run_number}_{product}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"download_invalid_rows_run{run_number}_{product}",
                    )

                    # Create action buttons
                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button(
                            "Continue with cleaned data",
                            key=f"filter_button_run{run_number}_{product}",
                        ):
                            st.warning(
                                f"Proceeding with {len(cleaned_df)} valid rows. {len(invalid_rows)} rows will be excluded."
                            )
                            st.session_state.batch_validation_state[run_number][
                                product
                            ] = {
                                "validated": True,
                                "mpf_data": cleaned_df,
                            }
                            print(
                                "\nFinal batch_validation_state:",
                                st.session_state.batch_validation_state,
                            )
                            st.rerun()

                    with col2:
                        if st.button(
                            "Continue with original data",
                            key=f"continue_button_run{run_number}_{product}",
                        ):
                            st.warning(
                                "Proceeding with original data including invalid rows."
                            )
                            st.session_state.batch_validation_state[run_number][
                                product
                            ] = {
                                "validated": True,
                                "mpf_data": current_mpf_data,
                            }
                            print(
                                "\nFinal batch_validation_state:",
                                st.session_state.batch_validation_state,
                            )
                            st.rerun()

                    # Add a separator between products
                    st.markdown("---")

            # Return validation status
            return all_validated

        except Exception as e:
            st.error(f"Error during MPF validation for run #{run_number}: {str(e)}")
            logger.warning(
                f"MPF Validation error in run #{run_number}: {str(e)}", exc_info=True
            )
            # Reset validation state for this run
            st.session_state.batch_validation_state[run_number] = {}
            return False


def check_products_validated(config, run_number):
    """Check if all products in a configuration are validated"""
    if run_number not in st.session_state.batch_validation_state:
        return False

    for product in config["product_groups"]:
        if product not in st.session_state.batch_validation_state[
            run_number
        ] or not st.session_state.batch_validation_state[run_number][product].get(
            "validated", False
        ):
            return False
    return True


def display_batch_validation_results(configurations):
    """Display validation results for all batch run configurations and handle user actions"""
    st.subheader("Batch Validation Results")
    # Track if all configurations are validated
    all_configs_validated = True

    # Process each configuration
    for config in configurations:
        run_number = config["run_number"]

        # Create an expander for this configuration
        with st.expander(f"Configuration #{run_number}", expanded=True):
            # Display configuration details
            st.write("Configuration details:")
            config_df = pd.DataFrame([config])
            st.dataframe(config_df)

            # Check if all products in this configuration are validated
            if check_products_validated(config, run_number):
                st.success(
                    f"✅ All validation checks passed for configuration #{run_number}!"
                )
                continue

            # If not validated, run validation
            try:
                all_validated = validate_batch_mpf(config, run_number)
                if not all_validated:
                    all_configs_validated = False

            except Exception as e:
                st.error(f"Error validating configuration #{run_number}: {str(e)}")
                logger.warning(
                    f"Validation error in configuration #{run_number}: {str(e)}",
                    exc_info=True,
                )
                all_configs_validated = False

    # If all configurations are validated, show a button to proceed with the batch run
    if all_configs_validated:
        st.success("✅ All configurations have passed validation!")
        if st.button("Proceed with Batch Run"):
            # Set a flag to indicate we're moving to the processing phase
            st.rerun()
    else:
        st.warning(
            "⚠️ Some configurations have validation issues. Please resolve them before proceeding."
        )

        # Add a button to cancel the batch run
        if st.button("Cancel Batch Run"):
            st.session_state.batch_validation_state = {}
            st.session_state.batch_run_button_clicked = False
            st.rerun()


def process_single_model_point_LS(
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
    model = initialize_model_LS(assumptions, model_points_df, proj_period, val_date)

    current_step += 1
    progress_bar.progress(current_step / total_steps)

    # Process and save results
    pv_df = model.Results.pv_results(0)
    analytics_df = model.Results.analytics()
    rpg_aggregation_df = model.Results.RPG_aggregation(0)

    model.close()

    model_results = {
        "present_value": pv_df,
        "analytics": analytics_df,
        "rpg_aggregation": rpg_aggregation_df,
        "model_points_count": len(model_points_df),
        "results_count": len(pv_df),
    }
    status_text.empty()

    return model_results, current_step


def process_single_model_point_IP(
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
    model = initialize_model_IP(assumptions, model_points_df, proj_period, val_date)

    current_step += 1
    progress_bar.progress(current_step / total_steps)

    # Process and save results
    pv_df = model.Results.cashflow_output_t0()
    print(pv_df)
    rpg_aggregation_df = model.Results.rpg_aggregate()
    model.close()

    model_results = {
        "present_value": pv_df,
        "rpg_aggregation": rpg_aggregation_df,
        "model_points_count": len(model_points_df),
        "results_count": len(pv_df),
    }
    status_text.empty()

    return model_results, current_step


def format_results_LS(model_results):
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
        model_results["analytics"].to_excel(writer, sheet_name="analytics", index=False)
        model_results["present_value"].to_excel(
            writer, sheet_name="present_value", index=False
        )
        model_results["rpg_aggregation"].to_excel(
            writer, sheet_name="rpg_aggregation", index=False
        )
    return output_buffer


def format_results_IP(model_results):
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
        if "analytics" in model_results:
            model_results["analytics"].to_excel(
                writer, sheet_name="analytics", index=False
            )

        model_results["present_value"].to_excel(
            writer, sheet_name="present_value", index=False
        )
        model_results["rpg_aggregation"].to_excel(
            writer, sheet_name="rpg_aggregation", index=False
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
            st.write("RPG Aggregation:")
            st.write(product_results["rpg_aggregation"])


def process_model_run(settings_dict):
    """Process the model run and display results"""
    results = {}

    # Convert settings dictionary to ModelSettings object
    settings = ModelSettings.from_dict(settings_dict)
    settings.validate()  # Validate settings
    validation_text = st.empty()
    validation_text.success("Settings validated! Ready to run valuation model.")

    # Initialize progress tracking
    progress_bar, status_text, time_text = initialize_progress_indicators()
    start_time = datetime.datetime.now()
    output_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    with st.spinner("Running valuation model..."):
        try:
            # Get appropriate model handler
            results = {}
            handler = get_model_handler(
                st.session_state.get("storage_type", "SharePoint")
            )

            # Download and process input files
            status_text.text("Downloading and processing input files...")
            print("downloading ..........")
            cached_download_model(settings.models_url, settings.model_name)

            if "IP" in settings.model_name:
                assumptions = cached_download_assumptions_IP(settings.assumption_url)
                model_points_list = cached_download_model_points(
                    settings.model_points_url, settings.product_groups
                )
                print("Finished downloading")
                # Initialize tracking variables
                total_steps = len(settings.product_groups) * 2
                current_step = 0
                progress_bar.progress(current_step / total_steps)

                for product_idx, product in enumerate(settings.product_groups, 1):
                    # Process each product
                    # Make sure we're using the validated MPF data
                    if (
                        product in st.session_state.validation_state
                        and "mpf_data" in st.session_state.validation_state[product]
                    ):
                        model_points_df = st.session_state.validation_state[product][
                            "mpf_data"
                        ]
                    else:
                        # Fallback to original data if validation state is missing
                        model_points_df = model_points_list.get(product)
                        st.warning(
                            f"Using unvalidated data for {product}. This may cause issues."
                        )

                    model_result, current_step = process_single_model_point_IP(
                        product=product,
                        product_idx=product_idx,
                        settings=settings_dict,
                        model_points_df=model_points_df,
                        assumptions=assumptions,
                        total_products=len(settings.product_groups),
                        progress_bar=progress_bar,
                        current_step=current_step,
                        total_steps=total_steps,
                    )

                    current_step += 1
                    progress_bar.progress(current_step / total_steps)

                    output_buffer = format_results_IP(model_result)
                    output_filename = f"results_{product}_{output_timestamp}.xlsx"
                    output_path = (
                        f"{settings.results_url.rstrip('/')}/{output_filename}"
                    )
                    handler.save_results(output_buffer.getvalue(), output_path)
                    results[product] = model_result

            else:
                assumptions = cached_download_assumptions_LS(settings.assumption_url)
                print("downloading model points LS")
                model_points_list = cached_download_model_points(
                    settings.model_points_url, settings.product_groups
                )
                # Initialize tracking variables
                total_steps = len(settings.product_groups) * 2  # 2 steps per product
                current_step = 0
                progress_bar.progress(current_step / total_steps)
                results = {}

                for product_idx, product in enumerate(settings.product_groups, 1):
                    # 确保使用已验证的 MPF 数据
                    if (
                        product in st.session_state.validation_state
                        and "mpf_data" in st.session_state.validation_state[product]
                    ):
                        model_points_df = st.session_state.validation_state[product][
                            "mpf_data"
                        ]
                    else:
                        # 如果验证状态缺失，则使用原始数据
                        model_points_df = model_points_list.get(product)
                        st.warning(
                            f"Using unvalidated data for {product}. This may cause issues."
                        )

                    model_result, current_step = process_single_model_point_LS(
                        product=product,
                        product_idx=product_idx,
                        settings=settings_dict,  # Pass the original dict for logging
                        model_points_df=model_points_df,
                        assumptions=assumptions,
                        total_products=len(settings.product_groups),
                        progress_bar=progress_bar,
                        current_step=current_step,
                        total_steps=total_steps,
                    )

                    current_step += 1
                    progress_bar.progress(current_step / total_steps)

                    output_buffer = format_results_LS(model_result)
                    output_filename = f"results_{product}_{output_timestamp}.xlsx"
                    output_path = (
                        f"{settings.results_url.rstrip('/')}/{output_filename}"
                    )
                    handler.save_results(output_buffer.getvalue(), output_path)
                    results[product] = model_result

            # Calculate total time
            end_time = datetime.datetime.now()
            total_time = (end_time - start_time).total_seconds()

            # Log successful run
            logger.create_run_log(
                settings=settings_dict,  # Use the original dict for logging
                start_time=start_time,
                end_time=end_time,
                status="success",
                output_location=settings.results_url,
            )
            validation_text.empty()

            # Clear progress indicators and display results
            clear_progress_indicators(progress_bar, status_text, time_text)

            st.session_state["results"] = results
            st.success(f"Model run completed successfully in {total_time:.1f} seconds!")
            if st.session_state.get("storage_type") == "SharePoint":
                output_file_url = handler.get_file_url(settings.results_url)
                st.write("Results saved to URL: %s" % output_file_url)
            else:
                st.write("Results saved to: %s" % settings.results_url)

        except Exception as e:
            # Clear progress indicators
            clear_progress_indicators(progress_bar, status_text, time_text)

            end_time = datetime.datetime.now()
            # Log failed run
            logger.create_run_log(
                settings=settings_dict,  # Use the original dict for logging
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
    rpg_aggregation = []  # List to store all results for stacking
    summary_results = []

    for config in configurations:
        st.write(f"Running configuration: {config['run_number']}")
        try:
            # Convert date strings to date objects
            if isinstance(config.get("valuation_date"), str):
                config["valuation_date"] = convert_date_string(config["valuation_date"])
            # Convert product_groups to a list if it's a string
            config["product_groups"] = convert_to_list(config.get("product_groups", []))
            config["projection_period"] = int(config["projection_period"])

            # Get the run number for this configuration
            run_number = config["run_number"]

            # 检查该配置的所有产品是否已验证
            all_products_validated = True
            if run_number in st.session_state.batch_validation_state:
                for product in config["product_groups"]:
                    if product not in st.session_state.batch_validation_state[
                        run_number
                    ] or not st.session_state.batch_validation_state[run_number][
                        product
                    ].get(
                        "validated", False
                    ):
                        all_products_validated = False
                        st.error(
                            f"Product {product} in run #{run_number} has not been validated. Cannot proceed."
                        )
                        break
            else:
                all_products_validated = False
                st.error(f"Run #{run_number} has not been validated. Cannot proceed.")

            # 只有当所有产品都已验证时才继续
            if not all_products_validated:
                st.warning(f"Skipping run #{run_number} due to validation issues.")
                continue

            # Use the validated MPF data from the batch validation state
            for product in config["product_groups"]:
                if product in st.session_state.batch_validation_state[run_number]:
                    product_state = st.session_state.batch_validation_state[run_number][
                        product
                    ]
                    if "mpf_data" in product_state:
                        # Store the validated MPF data in the validation_state for process_model_run to use
                        if "validation_state" not in st.session_state:
                            st.session_state.validation_state = {}
                        st.session_state.validation_state[product] = {
                            "validated": True,
                            "mpf_data": product_state["mpf_data"],
                        }

            # Run the model with the validated data
            process_model_run(config)

            if "results" not in st.session_state:
                st.info("Run model to display the results")
            else:
                display_results(st.session_state["results"])
                # Collect results for stacking

                # add results to rpg_aggregation
                for product, result in st.session_state["results"].items():
                    result["rpg_aggregation"].insert(
                        0,
                        "run_number",
                        [config["run_number"]] * len(result["rpg_aggregation"]),
                    )
                    rpg_aggregation.append(result["rpg_aggregation"])
                # add summary to summary_results
                sum_present_values = []
                for product, result in st.session_state["results"].items():
                    sum_present_values.append(result["present_value"])
                    print(result["present_value"].columns)
                print("=================================")
                print(sum_present_values)
                combined_present_value = pd.concat(
                    sum_present_values, ignore_index=True
                )
                sums = combined_present_value.select_dtypes(
                    include=["float64", "int64"]
                ).sum()
                formatted_sums = sums.apply(lambda x: f"{x:,.2f}")

            # 创建与 rpg_aggregation 类似格式的 DataFrame
            summary_df = pd.DataFrame(
                {
                    "run_number": config["run_number"],
                    "Variable": formatted_sums.index,
                    "Value": formatted_sums.values,
                }
            )
            print("=================================")
            print(summary_df)
            summary_results.append(summary_df)

            st.success(f"Run {config['run_number']} completed successfully!")
        except Exception as e:
            st.error(f"Error in run {config['run_number']}: {str(e)}")

    # Stack all RPG aggregation results and export to Excel
    if rpg_aggregation and summary_results:
        stacked_results = pd.concat(rpg_aggregation, ignore_index=True)
        all_summary_results = pd.concat(summary_results, ignore_index=True)
        # Rename columns to ensure consistent naming
        stacked_results = stacked_results.rename(
            columns={
                "variable": "Variable",
                "value": "Value",
            }
        )
        stacked_results["Value"] = (
            stacked_results["Value"]
            .str.replace(",", "")  # 移除千分位逗号
            .str.replace("(", "-")  # 将左括号替换为负号
            .str.replace(")", "")  # 移除右括号
            .astype(float)
        )  # 转换为浮点数

        # stacked_results RPG Level group by Variable
        stacked_results_rpg = (
            stacked_results.groupby(["run_number", "Variable"])["Value"]
            .sum()
            .reset_index()
        )

        all_summary_results["Value"] = all_summary_results["Value"].apply(
            lambda x: float(str(x).replace(",", "").replace("(", "-").replace(")", ""))
            if isinstance(x, str)
            else float(x)
        )
        # 合并 stacked_results 和 all_summary_results
        comparison_df = pd.merge(
            stacked_results_rpg,
            all_summary_results,
            left_on=["run_number", "Variable"],
            right_on=["run_number", "Variable"],
            how="inner",
            suffixes=("_RPG", "_PV"),
        )
        comparison_df["Difference"] = (
            comparison_df["Value_RPG"] - comparison_df["Value_PV"]
        )
        print("=================================")
        print(comparison_df)

        summary_results = (
            stacked_results.groupby(["RPG", "Variable"])["Value"].sum().reset_index()
        )

        # 格式化结果：负数用括号，正数保持原样，都带千分位
        summary_results["Value"] = summary_results["Value"].apply(
            lambda x: f"({abs(x):,.2f})" if x < 0 else f"{x:,.2f}"
        )
        # 将数值格式化为带千分位的字符串
        output_buffer = io.BytesIO()
        with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
            summary_results.to_excel(
                writer, sheet_name="RPG Aggregation Summary", index=False
            )
            stacked_results.to_excel(
                writer, sheet_name="RPG Aggregation Each Run", index=False
            )
            comparison_df.to_excel(writer, sheet_name="Comparison", index=False)

        output_filename = f"batch_results_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
        # Get the parent directory by splitting the path and taking all but the last component
        base_path = "/".join(
            configurations[0]["results_url"].rstrip("/").split("/")[:-2]
        )
        output_path = f"{base_path}/{output_filename}"

        handler = get_model_handler(st.session_state.get("storage_type", "SharePoint"))
        handler.save_results(output_buffer.getvalue(), output_path)
        st.success(f"Batch results saved to: {output_path}")


def main():
    """Main application function"""
    # Check authentication
    if not authenticate_user():
        display_login()
        return
    # Initialize session state variables
    if "validation_state" not in st.session_state:
        st.session_state.validation_state = {}
    if "run_botton_clicked" not in st.session_state:
        st.session_state.run_botton_clicked = False
    if "batch_run_button_clicked" not in st.session_state:
        st.session_state.batch_run_button_clicked = False

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
        saved_settings = load_config()
        with st.expander("Settings Management"):
            # Storage configuration section
            storage_type = st.radio(
                "Select Storage Type", options=["SharePoint", "S3"], horizontal=True
            )
            # File selection based on storage type
            st.session_state["storage_type"] = storage_type
            if "run_botton_clicked" not in st.session_state:
                st.session_state.run_botton_clicked = False
            url_settings = display_settings_management(saved_settings)

        # Create main form for inputs
        if storage_type == "S3":
            settings = collect_S3_inputs(url_settings)
        else:
            settings = collect_sharepoint_inputs(saved_settings)

        # Form buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submitted = st.button("Run Model", on_click=callback)

        # Handle form submission
        if submitted or st.session_state.run_botton_clicked:
            # Initialize validation state if needed
            if "validation_state" not in st.session_state:
                st.session_state.validation_state = {}

            # Check if all products are already validated
            all_validated = all(
                st.session_state.validation_state.get(product, {}).get(
                    "validated", False
                )
                for product in settings.get("product_groups", [])
            )
            # If not all validated, run validation
            if not all_validated:
                all_validated = validate_all_mpf(settings)

            # If all validated, run the model
            if all_validated:
                process_model_run(settings)
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

                # Ensure each configuration has a run_number
                if "run_number" not in df.columns:
                    df["run_number"] = range(1, len(df) + 1)

                configurations = df.to_dict(orient="records")
                st.write("Configuration loaded successfully!")
                st.dataframe(df)  # Display the configurations for confirmation

                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    batch_submitted = st.button("Run Batch", on_click=callback_batch)

                if batch_submitted:
                    # Initialize batch validation state if not already present
                    st.session_state.batch_validation_state = {}
                    print("restart batch validation state")

                # Handle batch form submission
                if batch_submitted or st.session_state.batch_run_button_clicked:
                    print(st.session_state.batch_validation_state)
                    # Check if all configurations are already validated
                    all_configs_validated = True
                    for config in configurations:
                        config["product_groups"] = convert_to_list(
                            config.get("product_groups", [])
                        )
                        run_number = config["run_number"]
                        if run_number not in st.session_state.batch_validation_state:
                            all_configs_validated = False
                            print(1)
                            break

                        for product in config["product_groups"]:
                            if product not in st.session_state.batch_validation_state[
                                run_number
                            ] or not st.session_state.batch_validation_state[
                                run_number
                            ][
                                product
                            ].get(
                                "validated", False
                            ):
                                print(
                                    st.session_state.batch_validation_state[run_number][
                                        product
                                    ].get("validated")
                                )
                                all_configs_validated = False
                                print(2)
                                break

                    # If not all validated, run validation
                    if not all_configs_validated:
                        display_batch_validation_results(configurations)
                    print("all_configs_validated  : ", all_configs_validated)
                    # If all validated, run the batch processing
                    if all_configs_validated:
                        st.subheader("Model Results")
                        process_batch_run(configurations)
                        if "results" not in st.session_state:
                            st.info("Run batch to display the results")
                        else:
                            for config in configurations:
                                run_number = config["run_number"]
                                st.write(f"Results for Run #{run_number}:")
                                display_results(st.session_state["results"])

                    print(st.session_state.batch_validation_state)
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
