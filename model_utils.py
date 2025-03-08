import pandas as pd
import modelx as mx

import logging
from abc import ABC, abstractmethod
from typing import Dict, BinaryIO
import os

from IP_process import transform_assumptions

logger = logging.getLogger(__name__)

MODEL_PATH = "./tmp/models"


class ModelDataHandler(ABC):
    """Abstract base class for model operations"""

    @abstractmethod
    def download_assumptions_LS(self, url: str) -> Dict[str, pd.DataFrame]:
        """Download assumption tables from storage"""
        pass

    @abstractmethod
    def download_assumptions_IP(self, url: str) -> Dict[str, pd.DataFrame]:
        """Download assumption tables from storage"""
        pass

    @abstractmethod
    def download_model_points(
        self, url: str, product_groups: list
    ) -> Dict[str, pd.DataFrame]:
        """Download model points from storage"""
        pass

    @abstractmethod
    def download_model(
        self, models_url: str, model_name: str, local_path: str = MODEL_PATH
    ) -> None:
        """Download model from storage to local path"""
        pass

    @abstractmethod
    def save_results(self, content: BinaryIO, output_path: str) -> str:
        """Save results to storage"""
        pass


class S3ModelDataHandler(ModelDataHandler):
    """S3 implementation of model operations"""

    def __init__(self):
        from s3_utils import S3Client

        self.s3_client = S3Client()

    def download_assumptions_LS(self, url: str) -> Dict[str, pd.DataFrame]:
        # download the one file in the folder
        files = self.s3_client.list_files(url)
        assumption_file = self.s3_client.download_file(f"{url}/{files[0]}")
        return {
            "lapse_rate_table": pd.read_excel(assumption_file, sheet_name="lapse"),
            "inflation_rate_table": pd.read_excel(assumption_file, sheet_name="CPI"),
            "prem_exp_table": pd.read_excel(
                assumption_file, sheet_name="prem expenses"
            ),
            "fixed_exp_table": pd.read_excel(
                assumption_file, sheet_name="fixed expenses"
            ),
            "comm_table": pd.read_excel(assumption_file, sheet_name="commissions"),
            "disc_curve": pd.read_excel(assumption_file, sheet_name="discount curve"),
            "mort_table": pd.read_excel(assumption_file, sheet_name="mortality"),
            "trauma_table": pd.read_excel(assumption_file, sheet_name="trauma"),
            "tpd_table": pd.read_excel(assumption_file, sheet_name="TPD"),
            "prem_rate_level_table": pd.read_excel(
                assumption_file, sheet_name="prem_rate_level"
            ),
            "prem_rate_stepped_table": pd.read_excel(
                assumption_file, sheet_name="prem_rate_stepped"
            ),
            "RA_table": pd.read_excel(assumption_file, sheet_name="RA"),
            "RI_prem_rate_level_table": pd.read_excel(
                assumption_file, sheet_name="RI_prem_rate_level"
            ),
            "RI_prem_rate_stepped_table": pd.read_excel(
                assumption_file, sheet_name="RI_prem_rate_stepped"
            ),
        }

    def download_assumptions_IP(self, url: str) -> Dict[str, pd.DataFrame]:
        # download all files in the folder
        files = self.s3_client.list_files(url)
        assumptions_dict = {}
        for file in files:
            if file.endswith(".xlsx") or file.endswith(".xls"):
                assumption_file = self.s3_client.download_file(f"{url}/{file}")
                # Get all sheet names
                excel_file = pd.ExcelFile(assumption_file)

                # Read each sheet into the dictionary
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(assumption_file, sheet_name=sheet_name)
                    assumptions_dict[sheet_name] = df
        transformed_dict = transform_assumptions(assumptions_dict)
        return transformed_dict

    def download_model_points(
        self, url: str, product_groups: list
    ) -> Dict[str, pd.DataFrame]:
        files = self.s3_client.list_files(url)
        model_points_dict = {}
        for file in files:
            if file.endswith(".xlsx") and file in product_groups:
                # Remove any leading/trailing slashes from url and file
                clean_url = url.rstrip("/")
                clean_file = file.lstrip("/")

                file_url = f"{clean_url}/{clean_file}"
                file_content = self.s3_client.download_file(file_url)
                df = pd.read_excel(file_content)
                model_points_dict[file] = df
        return model_points_dict

    def download_model(
        self, models_url: str, model_name: str, local_path: str = MODEL_PATH
    ) -> None:
        self.s3_client.download_folder(models_url, model_name, local_path)

    def save_results(self, content: BinaryIO, output_path: str) -> str:
        return self.s3_client.upload_file(content, output_path)


class SharePointModelDataHandler(ModelDataHandler):
    """SharePoint implementation of model operations"""

    def __init__(self):
        from sharepoint_utils import SharePointClient

        self.sp_client = SharePointClient()

    def download_assumptions_LS(self, url: str) -> Dict[str, pd.DataFrame]:
        # download the one file in the folder
        files = self.sp_client.list_files(url)
        assumption_file = self.sp_client.download_file(f"{url}/{files[0]}")
        return {
            "lapse_rate_table": pd.read_excel(assumption_file, sheet_name="lapse"),
            "inflation_rate_table": pd.read_excel(assumption_file, sheet_name="CPI"),
            "prem_exp_table": pd.read_excel(
                assumption_file, sheet_name="prem expenses"
            ),
            "fixed_exp_table": pd.read_excel(
                assumption_file, sheet_name="fixed expenses"
            ),
            "comm_table": pd.read_excel(assumption_file, sheet_name="commissions"),
            "disc_curve": pd.read_excel(assumption_file, sheet_name="discount curve"),
            "mort_table": pd.read_excel(assumption_file, sheet_name="mortality"),
            "trauma_table": pd.read_excel(assumption_file, sheet_name="trauma"),
            "tpd_table": pd.read_excel(assumption_file, sheet_name="TPD"),
            "prem_rate_level_table": pd.read_excel(
                assumption_file, sheet_name="prem_rate_level"
            ),
            "prem_rate_stepped_table": pd.read_excel(
                assumption_file, sheet_name="prem_rate_stepped"
            ),
            "RA_table": pd.read_excel(assumption_file, sheet_name="RA"),
            "RI_prem_rate_level_table": pd.read_excel(
                assumption_file, sheet_name="RI_prem_rate_level"
            ),
            "RI_prem_rate_stepped_table": pd.read_excel(
                assumption_file, sheet_name="RI_prem_rate_stepped"
            ),
        }

    def download_assumptions_IP(self, url: str) -> Dict[str, pd.DataFrame]:
        # download all files in the folder
        files = self.sp_client.list_files(url)
        assumptions_dict = {}
        for file in files:
            if file.endswith(".xlsx") or file.endswith(".xls"):
                assumption_file = self.sp_client.download_file(f"{url}/{file}")
                # Get all sheet names
                excel_file = pd.ExcelFile(assumption_file)

                # Read each sheet into the dictionary
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(assumption_file, sheet_name=sheet_name)
                    assumptions_dict[sheet_name] = df
        transformed_dict = transform_assumptions(assumptions_dict)
        return transformed_dict

    def download_model_points(
        self, url: str, product_groups: list
    ) -> Dict[str, pd.DataFrame]:
        files = self.sp_client.list_files(url)

        model_points_dict = {}
        for file in files:
            if file.endswith(".xlsx") and file in product_groups:
                file_content = self.sp_client.download_file(f"{url}/{file}")
                df = pd.read_excel(file_content)
                model_points_dict[file] = df
        return model_points_dict

    def download_model(
        self, models_url: str, model_name: str, local_path: str = MODEL_PATH
    ) -> None:
        model_path = f"{models_url}/{model_name}"
        if not os.path.exists(local_path):
            os.makedirs(local_path)

        self.sp_client.download_folder(model_path, local_path)

    def save_results(self, content: BinaryIO, output_path: str) -> str:
        return self.sp_client.upload_file(content, output_path)

    def get_file_url(self, file_path: str) -> str:
        return self.sp_client.get_file_url(file_path)


def get_model_handler(storage_type: str) -> ModelDataHandler:
    """Factory function to get appropriate model handler"""
    if storage_type == "S3":
        return S3ModelDataHandler()
    elif storage_type == "SharePoint":
        return SharePointModelDataHandler()
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")


def initialize_model_LS(
    assumptions: Dict[str, pd.DataFrame],
    model_points_df: pd.DataFrame,
    proj_period: int,
    val_date: str,
    model_path: str = MODEL_PATH,
) -> mx:
    """Initialize and configure the modelx model"""
    # Initialize model
    model = mx.read_model(model_path)
    model.Data_Inputs.proj_period = proj_period
    model.Data_Inputs.val_date = val_date

    for attribute, dataframe in assumptions.items():
        setattr(model.Data_Inputs, attribute, dataframe)

    # Set model points
    model.Data_Inputs.model_point_table = model_points_df

    return model


def initialize_model_IP(
    assumptions: Dict[str, pd.DataFrame],
    model_points_df: pd.DataFrame,
    proj_period: int,
    val_date: str,
    model_path: str = MODEL_PATH,
) -> mx:
    """Initialize and configure the modelx model"""
    # Initialize model
    model = mx.read_model(model_path)

    # Update Mapping Tables
    model.Mapping.Occupation = assumptions["Occupation"]
    model.Mapping.Waiting_period = assumptions["Waiting_period"]
    model.Mapping.Smoker = assumptions["Smoker"]
    model.Mapping.Benefit_period = assumptions["Benefit_period"]
    model.Mapping.Prem_payment_freq = assumptions["Prem_payment_freq"]

    # Update Assumption Tables
    # Reference Tables
    model.Assumptions.Mortality = assumptions["Mortality"]
    model.Assumptions.Lapse = assumptions["Lapse"]
    model.Assumptions.TPD = assumptions["TPD"]
    model.Assumptions.Trauma = assumptions["Trauma"]
    model.Assumptions.Prem_Rate_Level = assumptions["Prem_rate_level"]
    model.Assumptions.Prem_Rate_Stepped = assumptions["Prem_rate_stepped"]
    model.Assumptions.Rein_Prem_Rate_Level = assumptions["Rein_Prem_rate_level"]
    model.Assumptions.Rein_Prem_Rate_Stepped = assumptions["Rein_Prem_rate_stepped"]

    # Economic Assumptions
    model.Assumptions.Mth_Discount_rate = assumptions["Monthly_discount_rates"]
    model.Assumptions.Inflation = assumptions["Inflation"]
    model.Assumptions.Forward_rate = assumptions["Forward_rate"]

    # Expense and Commission
    model.Assumptions.Commission_rate = assumptions["Commission_rates"]
    model.Assumptions.Prem_related_expenses = assumptions["Prem_related_expenses"]
    model.Assumptions.Fixed_expenses = assumptions["Fixed_expenses"]
    model.Assumptions.Risk_adj_pc = assumptions["Risk_adj_pc"]
    model.Assumptions.Valuation_Variables = assumptions["Variables"]

    # Death Only Tables
    model.Assumptions.Death_Only_Mort_Age_Rates = assumptions[
        "Death_Only_Mort_Age_Rates"
    ]
    model.Assumptions.Death_Only_Duration_Loading = assumptions[
        "Death_Only_Duration_Loading"
    ]
    model.Assumptions.Death_Only_Mortality_Floor = assumptions[
        "Death_Only_Mortality_Floor"
    ]

    # Incidence Tables
    model.Assumptions.Incidence_Age_Rates_Female = assumptions[
        "Incidence_Age_Rates_Female"
    ]
    model.Assumptions.Incidence_Age_Rates_Male = assumptions["Incidence_Age_Rates_Male"]
    model.Assumptions.Incidence_Lifetime_Benefit_Period = assumptions[
        "Incidence_Lifetime_Benefit_Period"
    ]
    model.Assumptions.Incidence_Waiting_Period = assumptions["Incidence_Waiting_Period"]
    model.Assumptions.Incidence_Smoking_Status = assumptions["Incidence_Smoking_Status"]
    model.Assumptions.Incidence_Benefit_Type = assumptions["Incidence_Benefit_Type"]
    model.Assumptions.Incidence_Duration_Loading = assumptions[
        "Incidence_Duration_Loading"
    ]
    model.Assumptions.Incidence_Age_Rates_Sickness_Combined = assumptions[
        "Incidence_Age_Rates_Sickness_Combined"
    ]

    # Termination Tables
    model.Assumptions.Termination_Age_Rates = assumptions["Termination_Age_Rates"]
    model.Assumptions.Termination_Duration_Claim_Acc = assumptions[
        "Termination_Duration_Claim_Acc"
    ]
    model.Assumptions.Termination_Duration_Claim_Sick = assumptions[
        "Termination_Duration_Claim_Sick"
    ]
    model.Assumptions.Termination_Smoker = assumptions["Termination_Smoker"]
    model.Assumptions.Termination_Benefit_Type = assumptions["Termination_Benefit_Type"]
    model.Assumptions.Termination_Duration_Factor_Accident = assumptions[
        "Termination_Duration_Factor_Accident"
    ]
    model.Assumptions.Termination_Benefit_Period = assumptions[
        "Termination_Benefit_Period"
    ]
    model.Assumptions.Termination_Duration_Factor_Sickness = assumptions[
        "Termination_Duration_Factor_Sickness"
    ]
    model.Assumptions.Termination_New_Claim = assumptions["Termination_new_claim"]
    model.Assumptions.Termination_Cause_Sickness = assumptions[
        "Termination_cause_of_sickness"
    ]

    # Set model points
    model.MPF_inputs.MPF_inputs = model_points_df

    return model
