import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Tuple
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("MPF_Validator")


class MPFValidator:
    """Model Point File (MPF) Data Validator"""

    def __init__(
        self,
        df_mpf: pd.DataFrame,
        df_rules: pd.DataFrame = None,
        validation_date: str = None,
        product: str = "IP",
    ):
        """
        初始化MPF验证器

        Args:
            df_mpf: MPF数据DataFrame
            df_rules: 规则数据DataFrame，如果为None则需要在调用验证方法前设置
            validation_date: 验证日期，格式为YYYY-MM-DD，默认为今天
            product: 产品类型，默认为"IP"
        """
        # 创建输入DataFrame的深拷贝，避免修改原始数据
        self.df_mpf = df_mpf.copy(deep=True)
        self.df_rules = df_rules.copy(deep=True) if df_rules is not None else None
        self.product = product
        # 设置验证日期，默认为今天
        if validation_date:
            try:
                self.validation_date = datetime.strptime(
                    validation_date, "%Y-%m-%d"
                ).date()
            except ValueError:
                logger.error(
                    f"Invalid validation date format: {validation_date}. Using today's date."
                )
                self.validation_date = datetime.today().date()
        else:
            self.validation_date = datetime.today().date()

        # 存储验证结果
        self.validation_results = {}
        self.invalid_rows = set()

        logger.info(f"Initialized validator with {len(self.df_mpf)} MPF rows")
        if self.df_rules is not None:
            logger.info(f"Loaded {len(self.df_rules)} validation rules")

    def completeness_check(self) -> Dict:
        """检查所有列是否有空值、NaN或空字符串"""
        logger.info("Running completeness check...")

        # 识别包含NaN、空白或空字符串的列
        incomplete_columns = []
        for col in self.df_mpf.columns:
            # 检查 NaN 值
            has_nan = self.df_mpf[col].isna().any()

            # 检查空字符串 - 只对可以转换为字符串的列进行检查
            try:
                has_empty = False
                # 只对对象类型的列应用字符串操作
                if self.df_mpf[col].dtype == "object":
                    has_empty = self.df_mpf[col].astype(str).str.strip().eq("").any()
            except Exception as e:
                logger.warning(f"Error checking empty strings in column {col}: {e}")
                # 假设有问题，以便安全处理
                has_empty = True

            if has_nan or has_empty:
                incomplete_columns.append(col)

        # 如果没有不完整的列，直接返回成功
        if not incomplete_columns:
            result = {"status": "Success", "message": "All columns are complete."}
            self.validation_results["completeness"] = result
            return result

        # 找出有问题的行
        problem_rows = pd.DataFrame()
        for col in incomplete_columns:
            # 检查 NaN
            nan_rows = self.df_mpf[self.df_mpf[col].isna()]

            # 检查空字符串 - 只对可以转换为字符串的列进行检查
            empty_rows = pd.DataFrame()
            try:
                if self.df_mpf[col].dtype == "object":
                    empty_rows = self.df_mpf[
                        self.df_mpf[col].astype(str).str.strip() == ""
                    ]
            except Exception:
                # 忽略错误，继续处理
                pass

            # 合并结果
            problem_rows = pd.concat(
                [problem_rows, nan_rows, empty_rows]
            ).drop_duplicates()

        if not problem_rows.empty:
            self.invalid_rows.update(problem_rows.index.tolist())

            # 确保只选择存在的列
            cols_to_show = ["Policy number"]
            cols_to_show.extend(
                [col for col in incomplete_columns if col in problem_rows.columns]
            )

            result = {
                "status": "Error",
                "message": f"The following columns contain NaN, blank, or empty values: {', '.join(incomplete_columns)}",
                "affected_rows": problem_rows[cols_to_show].reset_index(drop=True),
            }
        else:
            result = {"status": "Success", "message": "All columns are complete."}

        self.validation_results["completeness"] = result
        return result

    def policy_number_check(self) -> Dict:
        """检查Policy number列是否有效且唯一"""
        logger.info("Running policy number check...")

        if "Policy number" not in self.df_mpf.columns:
            result = {
                "status": "Error",
                "message": "Error: 'Policy number' column is missing.",
            }
            self.validation_results["policy_number"] = result
            return result

        # 检查Policy number是否为整数
        non_int_rows = self.df_mpf[
            ~self.df_mpf["Policy number"].apply(lambda x: isinstance(x, int))
        ]

        # 找出重复的Policy number
        duplicate_rows = self.df_mpf[
            self.df_mpf["Policy number"].duplicated(keep=False)
        ]
        duplicates = self.df_mpf["Policy number"][
            self.df_mpf["Policy number"].duplicated(keep=False)
        ].unique()

        problem_rows = pd.concat([non_int_rows, duplicate_rows]).drop_duplicates()

        if not problem_rows.empty:
            self.invalid_rows.update(problem_rows.index.tolist())

            if not non_int_rows.empty and not duplicate_rows.empty:
                message = "Error: Some policy numbers are not integers and some are duplicated."
            elif not non_int_rows.empty:
                message = "Error: 'Policy number' column must contain only integers."
            else:
                message = f"Error: Policy Number must be unique. Duplicates found: {', '.join(map(str, duplicates))}"

            result = {
                "status": "Error",
                "message": message,
                "affected_rows": problem_rows[["Policy number"]].reset_index(drop=True),
            }
        else:
            result = {
                "status": "Success",
                "message": "All policy numbers are valid and unique.",
            }

        self.validation_results["policy_number"] = result
        return result

    def policy_term_check(self) -> Dict:
        """检查policy_term是否为大于0的整数"""
        logger.info("Running policy term check...")

        # 识别policy_term不是大于0的整数的行
        invalid_rows = self.df_mpf[
            (self.df_mpf["policy_term"] <= 0) | (self.df_mpf["policy_term"] % 1 != 0)
        ]

        if not invalid_rows.empty:
            self.invalid_rows.update(invalid_rows.index.tolist())
            result = {
                "status": "Error",
                "message": "Error: Some policy numbers have incorrect policy terms",
                "affected_rows": invalid_rows[
                    ["Policy number", "policy_term"]
                ].reset_index(drop=True),
            }
        else:
            result = {"status": "Success", "message": "All policy terms are correct."}

        self.validation_results["policy_term"] = result
        return result

    def numeric_amt_check(self) -> Dict:
        """检查所有数值金额列"""
        logger.info("Running numeric amount check...")
        if self.product == "IP":
            columns_to_check = [
                "sum_assured_dth",
                "sum_assured_tpd",
                "sum_assured_trm",
                "Annual Prem",
                "R_sum_assured_dth",
                "R_sum_assured_tpd",
                "R_sum_assured_trm",
                "R_Prem",
                "Monthly Benefit",
                "R_Monthly_Ben",
            ]
        else:
            columns_to_check = [
                "sum_assured_dth",
                "sum_assured_tpd",
                "sum_assured_trm",
                "Annual Prem",
                "R_sum_assured_dth",
                "R_sum_assured_tpd",
                "R_sum_assured_trm",
                "R_Prem",
            ]

        # 确保所有值都是数值且非负
        numeric_check = (
            self.df_mpf[columns_to_check]
            .apply(lambda x: pd.to_numeric(x, errors="coerce"))
            .fillna(-1)
        )

        invalid_rows = self.df_mpf[(numeric_check < 0).any(axis=1)]

        # 确保sum_assured_dth, Annual Prem, 和 Monthly Benefit大于零
        if self.product == "IP":
            mandatory_columns = ["sum_assured_dth", "Annual Prem", "Monthly Benefit"]
        else:
            mandatory_columns = ["sum_assured_dth", "Annual Prem"]
        mandatory_check = (
            self.df_mpf[mandatory_columns]
            .apply(lambda x: pd.to_numeric(x, errors="coerce"))
            .fillna(0)
        )

        invalid_mandatory_rows = self.df_mpf[(mandatory_check == 0).any(axis=1)]

        all_invalid_rows = pd.concat(
            [invalid_rows, invalid_mandatory_rows]
        ).drop_duplicates()

        if not all_invalid_rows.empty:
            self.invalid_rows.update(all_invalid_rows.index.tolist())
            result = {
                "status": "Error",
                "message": "Error: Some policy numbers have incorrect numeric amount values",
                "affected_rows": all_invalid_rows[
                    ["Policy number"] + columns_to_check
                ].reset_index(drop=True),
            }
        else:
            result = {
                "status": "Success",
                "message": "All numeric amount values are correct.",
            }

        self.validation_results["numeric_amt"] = result
        return result

    def dob_check(self) -> Dict:
        """检查DOB是否在有效范围内"""
        logger.info("Running DOB check...")

        today = datetime.today().date()
        min_date = today - timedelta(days=65 * 365)  # 65年前
        max_date = today - timedelta(days=18 * 365)  # 18年前

        # 创建临时列，而不是修改原始列
        dob_cleaned = self.df_mpf["DOB"].astype(str).str.strip()

        try:
            dob_dates = pd.to_datetime(dob_cleaned, errors="coerce").dt.date
            invalid_rows = self.df_mpf[
                (dob_dates.isna()) | (dob_dates < min_date) | (dob_dates > max_date)
            ]

            if not invalid_rows.empty:
                self.invalid_rows.update(invalid_rows.index.tolist())
                result = {
                    "status": "Error",
                    "message": "Error: Some policy numbers have incorrect DOB values",
                    "affected_rows": invalid_rows[["Policy number", "DOB"]].reset_index(
                        drop=True
                    ),
                }
            else:
                result = {"status": "Success", "message": "All DOB values are correct."}

        except Exception as e:
            result = {
                "status": "Error",
                "message": f"Error converting DOB: {e}",
                "affected_rows": self.df_mpf[["Policy number", "DOB"]],
            }

        self.validation_results["dob"] = result
        return result

    def entry_date_check(self) -> Dict:
        """检查Entry date是否在有效范围内"""
        logger.info("Running entry date check...")

        val_date = self.validation_date

        try:
            # 转换DOB和Entry date为日期
            dob_dates = pd.to_datetime(self.df_mpf["DOB"], errors="coerce").dt.date
            entry_dates = pd.to_datetime(
                self.df_mpf["Entry date"], errors="coerce"
            ).dt.date

            invalid_rows = self.df_mpf[
                (entry_dates.isna())
                | (entry_dates < dob_dates)
                | (entry_dates > val_date)
            ]

            if not invalid_rows.empty:
                self.invalid_rows.update(invalid_rows.index.tolist())
                result = {
                    "status": "Error",
                    "message": "Error: Some policy numbers have incorrect entry dates",
                    "affected_rows": invalid_rows[
                        ["Policy number", "Entry date"]
                    ].reset_index(drop=True),
                }
            else:
                result = {
                    "status": "Success",
                    "message": "All entry dates are correct.",
                }

        except Exception as e:
            result = {
                "status": "Error",
                "message": f"Error checking entry dates: {e}",
                "affected_rows": self.df_mpf[["Policy number", "Entry date"]],
            }

        self.validation_results["entry_date"] = result
        return result

    def generic_check(self, column_name: str) -> Dict:
        """根据规则检查特定列的值"""
        logger.info(f"Running generic check for {column_name}...")

        # 从规则中提取有效值并转换为集合
        valid_values_df = self.df_rules.loc[
            self.df_rules["Column"] == column_name, "Input_Array"
        ]

        if valid_values_df.empty:
            return {
                "status": "Warning",
                "message": f"No rules found for column {column_name}",
            }

        valid_values = set(valid_values_df.str.split(", ").explode())

        # 创建临时列进行比较，而不是修改原始列
        column_as_str = self.df_mpf[column_name].astype(str)

        # 识别具有无效值的行
        invalid_rows = self.df_mpf[~column_as_str.isin(valid_values)]

        if not invalid_rows.empty:
            self.invalid_rows.update(invalid_rows.index.tolist())
            result = {
                "status": "Error",
                "message": f"Error: Some policy numbers have incorrect {column_name} values",
                "affected_rows": invalid_rows[
                    ["Policy number", column_name]
                ].reset_index(drop=True),
            }
        else:
            result = {
                "status": "Success",
                "message": f"All {column_name} values are correct.",
            }

        return result

    def integer_check(self, column: str) -> Dict:
        """检查列是否为大于0的整数"""
        logger.info(f"Running integer check for {column}...")

        invalid_rows = self.df_mpf[
            (~self.df_mpf[column].apply(lambda x: isinstance(x, int)))
            | (self.df_mpf[column] <= 0)
        ]

        if not invalid_rows.empty:
            self.invalid_rows.update(invalid_rows.index.tolist())
            result = {
                "status": "Error",
                "message": f"Error: Some policy numbers have incorrect {column} values",
                "affected_rows": invalid_rows[["Policy number", column]].reset_index(
                    drop=True
                ),
            }
        else:
            result = {
                "status": "Success",
                "message": f"All {column} values are valid integers greater than zero.",
            }

        return result

    def check_all_columns(self) -> Dict:
        """检查所有列的规则"""
        logger.info("Running checks for all columns...")

        columns_to_check = [
            "Product",
            "sex",
            "pols_if_init",
            "Prem Freq",
            "Prem_Increase_ind",
            "Smoker status",
            "Stepped_ind",
            "Occupation",
            "Waiting Period",
            "Benefit Period Type",
            "Benefit Period",
            "Benefit Type",
            "Prem Waiver",
        ]

        integer_columns = [
            "IFRS17_Contract_Boundary",
            "IFRS17_Rein_Contract_Boundary",
            "Related_Policy_Group",
            "Related_Policy_Group_Rein",
        ]

        results = {}

        for column in columns_to_check:
            if column in self.df_mpf.columns:
                results[column] = self.generic_check(column)
            else:
                results[column] = {
                    "status": "Error",
                    "message": f"Column {column} not found in MPF data",
                }

        for column in integer_columns:
            if column in self.df_mpf.columns:
                results[column] = self.integer_check(column)
            else:
                results[column] = {
                    "status": "Error",
                    "message": f"Column {column} not found in MPF data",
                }

        self.validation_results["column_checks"] = results
        return results

    def run_all_checks(self) -> Dict:
        """运行所有验证检查"""
        logger.info("Running all validation checks...")

        self.completeness_check()
        self.policy_number_check()
        self.policy_term_check()
        self.numeric_amt_check()
        self.dob_check()
        self.entry_date_check()
        self.check_all_columns()

        return self.validation_results

    def get_invalid_rows(self) -> pd.DataFrame:
        """获取所有无效行"""
        if self.invalid_rows:
            return self.df_mpf.iloc[list(self.invalid_rows)].reset_index(drop=True)
        return pd.DataFrame()

    def remove_invalid_rows(self) -> pd.DataFrame:
        """移除所有无效行并返回清理后的数据框"""
        if self.invalid_rows:
            return self.df_mpf.drop(list(self.invalid_rows)).reset_index(drop=True)
        return self.df_mpf

    def get_cleaned_data(self) -> pd.DataFrame:
        """返回清理后的数据框"""
        return self.remove_invalid_rows()

    def save_cleaned_data(self, output_file: str) -> str:
        """保存清理后的数据到Excel文件"""
        if not output_file:
            raise ValueError("Output file path must be provided")

        cleaned_df = self.remove_invalid_rows()

        # 创建一个ExcelWriter对象
        with pd.ExcelWriter(output_file) as writer:
            # 写入清理后的MPF数据
            cleaned_df.to_excel(writer, sheet_name="MPF_Input", index=False)

            # 写入原始规则数据
            if self.df_rules is not None:
                self.df_rules.to_excel(writer, sheet_name="Rules_Input", index=False)

            # 写入验证结果
            validation_summary = []
            for check_name, result in self.validation_results.items():
                if check_name != "column_checks":
                    validation_summary.append(
                        {
                            "Check": check_name,
                            "Status": result.get("status", ""),
                            "Message": result.get("message", ""),
                        }
                    )
                else:
                    for col_name, col_result in result.items():
                        validation_summary.append(
                            {
                                "Check": f"{check_name} - {col_name}",
                                "Status": col_result.get("status", ""),
                                "Message": col_result.get("message", ""),
                            }
                        )

            pd.DataFrame(validation_summary).to_excel(
                writer, sheet_name="Validation_Results", index=False
            )

            # 写入移除的行
            invalid_rows_df = self.get_invalid_rows()
            if not invalid_rows_df.empty:
                invalid_rows_df.to_excel(writer, sheet_name="Removed_Rows", index=False)

        logger.info(f"Cleaned data saved to {output_file}")
        return output_file


def display_validation_results(results: Dict):
    """显示验证结果"""
    print("\n" + "=" * 80)
    print("MPF VALIDATION RESULTS")
    print("=" * 80)

    # 显示基本检查结果
    basic_checks = [k for k in results.keys() if k != "column_checks"]
    for check in basic_checks:
        result = results[check]
        status_symbol = "✅" if result["status"] == "Success" else "❌"
        print(f"{status_symbol} {check.upper()}: {result['message']}")

        if (
            result.get("affected_rows") is not None
            and not result["affected_rows"].empty
        ):
            print("\nAffected rows:")
            print(result["affected_rows"].to_string(index=False))
            print()

    # 显示列检查结果
    if "column_checks" in results:
        print("\n" + "-" * 80)
        print("COLUMN VALIDATION RESULTS")
        print("-" * 80)

        column_results = results["column_checks"]
        for column, result in column_results.items():
            status_symbol = "✅" if result["status"] == "Success" else "❌"
            print(f"{status_symbol} {column}: {result['message']}")

            if (
                result.get("affected_rows") is not None
                and not result["affected_rows"].empty
            ):
                print("\nAffected rows:")
                print(result["affected_rows"].to_string(index=False))
                print()


def validate_mpf_dataframe(
    df_mpf: pd.DataFrame,
    df_rules: pd.DataFrame = None,
    validation_date: str = None,
    product: str = "IP",
) -> Tuple[Dict, pd.DataFrame, pd.DataFrame]:
    """
    验证MPF DataFrame并返回验证结果和清理后的数据

    Args:
        df_mpf: MPF数据DataFrame
        df_rules: 规则数据DataFrame
        validation_date: 验证日期，格式为YYYY-MM-DD

    Returns:
        Tuple[Dict, pd.DataFrame, pd.DataFrame]: 验证结果、清理后的DataFrame和无效行DataFrame
    """
    # 创建验证器 - 不需要在这里创建副本，因为MPFValidator构造函数已经会创建副本
    validator = MPFValidator(
        df_mpf=df_mpf,
        df_rules=df_rules,
        validation_date=validation_date,
        product=product,
    )

    # 运行所有检查
    results = validator.run_all_checks()

    # 获取清理后的数据
    cleaned_df = validator.get_cleaned_data()

    return results, cleaned_df, validator.get_invalid_rows()
