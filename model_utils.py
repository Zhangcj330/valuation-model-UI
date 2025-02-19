import pandas as pd
import modelx as mx

import logging
from abc import ABC, abstractmethod
from typing import Dict, BinaryIO
import os

logger = logging.getLogger(__name__)

MODEL_PATH = "./tmp/models"


class ModelDataHandler(ABC):
    """Abstract base class for model operations"""

    @abstractmethod
    def download_assumptions(self, url: str) -> Dict[str, pd.DataFrame]:
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

    def download_assumptions(self, url: str) -> Dict[str, pd.DataFrame]:
        assumption_file = self.s3_client.download_file(url)
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

    def download_assumptions(self, url: str) -> Dict[str, pd.DataFrame]:
        assumption_file = self.sp_client.download_file(url)
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

    def download_model_points(
        self, url: str, product_groups: list
    ) -> Dict[str, pd.DataFrame]:
        # Implement SharePoint-specific model points downloading
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
        # Implement SharePoint-specific model download
        model_path = f"{models_url}/{model_name}"
        if not os.path.exists(local_path):
            os.makedirs(local_path)

        self.sp_client.download_folder(model_path, local_path)

    def save_results(self, content: BinaryIO, output_path: str) -> str:
        return self.sp_client.upload_file(content, output_path)


def get_model_handler(storage_type: str) -> ModelDataHandler:
    """Factory function to get appropriate model handler"""
    if storage_type == "S3":
        return S3ModelDataHandler()
    elif storage_type == "SharePoint":
        return SharePointModelDataHandler()
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")


def initialize_model(
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
