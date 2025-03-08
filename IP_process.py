import pandas as pd


def transform_assumptions(assumptions_dict):
    """
    Transform all assumption tables and return them in a dictionary

    Args:
        assumptions_dict: Dictionary of raw assumption DataFrames

    Returns:
        Dictionary of transformed DataFrames
    """
    transformed = {}

    mapping_tables = [
        "Occupation",
        "Waiting_period",
        "Smoker",
        "Benefit_period",
        "Prem_payment_freq",
    ]

    for table in mapping_tables:
        if table in assumptions_dict:
            transformed[table] = assumptions_dict[table]

    # 1. Simple direct assignments (no transformations needed)
    simple_tables = [
        "Mortality",
        "Lapse",
        "TPD",
        "Trauma",
        "Prem_rate_level",
        "Prem_rate_stepped",
        "Rein_Prem_rate_level",
        "Rein_Prem_rate_stepped",
        "Monthly_discount_rates",
        "Commission_rates",
        "Prem_related_expenses",
        "Fixed_expenses",
        "Risk_adj_pc",
        "Variables",
        "Termination_new_claim",
        "Termination_cause_of_sickness",
    ]

    for table in simple_tables:
        if table in assumptions_dict:
            transformed[table] = assumptions_dict[table]

    # 2. Death Only Mortality transformations
    df = assumptions_dict["DeathOnly_mort_age_rates"]
    Death_Only_Mort_Age_Rates = df.rename(
        columns={
            "Sex": "sex",
            "Age last birthday at last policy anniversary": "Age LB",
            "Non-smoker": "N",
            "Smoker": "S",
        }
    )
    Death_Only_Mort_Age_Rates = Death_Only_Mort_Age_Rates.drop(columns="Aggregate")
    transformed["Death_Only_Mort_Age_Rates"] = pd.melt(
        Death_Only_Mort_Age_Rates,
        id_vars=["Age LB", "sex"],
        var_name="Smoker status",
        value_name="Mortality Age Rates",
    )

    # 3. Death Only Duration Loading
    df = assumptions_dict["DeathOnly_duration_loading"]
    transformed["Death_Only_Duration_Loading"] = (
        pd.melt(
            df,
            id_vars=["Policy Duration (Curtate Years)"],
            var_name="sex",
            value_name="Duration Loading",
        )
        .assign(
            **{
                "Policy Duration (Curtate Years)": lambda x: x[
                    "Policy Duration (Curtate Years)"
                ].astype(str)
            }
        )
        .replace({"sex": {"Male": "M", "Female": "F"}})
    )

    # 4. Incidence Age Rates (Female)
    df = assumptions_dict["Incidence_age_rates_females"]
    transformed["Incidence_Age_Rates_Female"] = df.rename(
        columns={
            "Age": "Age LB",
            "Accident": "Accident Age Rates",
            "Sickness": "Sick Age Rates",
        }
    )

    # 5. Incidence Age Rates (Male)
    df = assumptions_dict["Incidence_age_rates_males"]
    male_rates = df.rename(columns={"Age": "Age LB"})
    transformed["Incidence_Age_Rates_Male"] = pd.melt(
        male_rates,
        id_vars=["Sex", "Age LB"],
        var_name="Accident Incidence Type",
        value_name="Accident Age Rates",
    ).replace(
        {
            "Accident Incidence Type": {
                "Accident Combined White Collar": "W",
                "Accident Combined Blue Collar": "B",
                "Sickness": "S",
            }
        }
    )[
        ["Age LB", "Sex", "Accident Incidence Type", "Accident Age Rates"]
    ]

    # 6. Incidence Lifetime Benefit Period
    df = assumptions_dict["Incidence_lifetime_bene_period"]
    transformed["Incidence_Lifetime_Benefit_Period"] = df.rename(
        columns={
            "Accident": "Accident Lifetime Factor",
            "Sickness": "Sick Lifetime Factor",
            "Sex": "sex",
        }
    )

    # 7. Incidence Waiting Period
    df = assumptions_dict["Incidence_waiting_period"]
    occupation_mapping = {
        "Professional/Medical": "P",
        "White Collar": "W",
        "Sedentary": "S",
        "Trades-person": "T",
        "Blue/Heavy Blue Collar": "B",
    }
    waiting_period = pd.melt(
        df,
        id_vars=["Type", "Sex", "Waiting_Period"],
        var_name="Occupation",
        value_name="Waiting Factor",
    )
    waiting_period["Occupation"] = waiting_period["Occupation"].map(occupation_mapping)
    transformed["Incidence_Waiting_Period"] = (
        waiting_period.pivot_table(
            index=["Sex", "Waiting_Period", "Occupation"],
            columns="Type",
            values="Waiting Factor",
        )
        .reset_index()
        .rename(
            columns={"Accident": "Accident Wait Factor", "Sickness": "Sick Wait Factor"}
        )
    )

    # 8. Incidence Smoking Status
    df = assumptions_dict["Incidence_smoking_status"]
    occupation_mapping = {
        "Combined White Collar": ["W", "P"],
        "Combined Blue Collar": ["S", "T", "B"],
    }

    smoking_status = pd.melt(
        df,
        id_vars=["Type", "Sex", "Smoking_Status"],
        var_name="Occupation Type",
        value_name="Smoker Factor",
    )

    expanded_rows = []
    for _, row in smoking_status.iterrows():
        occupation_codes = occupation_mapping[row["Occupation Type"]]
        for code in occupation_codes:
            new_row = row.copy()
            new_row["Occupation"] = code
            expanded_rows.append(new_row)

    smoking_status_transformed = pd.DataFrame(expanded_rows)
    smoking_status_transformed = smoking_status_transformed.drop(
        columns=["Occupation Type"]
    )
    transformed["Incidence_Smoking_Status"] = (
        smoking_status_transformed.pivot_table(
            index=["Sex", "Smoking_Status", "Occupation"],
            columns="Type",
            values="Smoker Factor",
        )
        .reset_index()
        .rename(
            columns={
                "Accident": "Accident Smoke Factor",
                "Sickness": "Sick Smoke Factor",
            }
        )
    )

    # 9. Incidence Benefit Type
    df = assumptions_dict["Incidence_benefit_type"]
    benefit_type_mapping = {"Agreed Value": "A", "Indemnity": "I"}

    benefit_type = pd.melt(
        df,
        id_vars=["Type", "Sex", "Benefit Type"],
        var_name="Occupation Type",
        value_name="Benefit Type Factor",
    )
    benefit_type["Benefit Type"] = benefit_type["Benefit Type"].map(
        benefit_type_mapping
    )

    expanded_rows = []
    for _, row in benefit_type.iterrows():
        occupation_codes = occupation_mapping[row["Occupation Type"]]
        for code in occupation_codes:
            new_row = row.copy()
            new_row["Occupation"] = code
            expanded_rows.append(new_row)

    benefit_type_transformed = pd.DataFrame(expanded_rows)
    benefit_type_transformed = benefit_type_transformed.drop(
        columns=["Occupation Type"]
    )
    transformed["Incidence_Benefit_Type"] = (
        benefit_type_transformed.pivot_table(
            index=["Sex", "Occupation", "Benefit Type"],
            columns="Type",
            values="Benefit Type Factor",
        )
        .reset_index()
        .rename(
            columns={
                "Accident": "Accident Benefit Type Factor",
                "Sickness": "Sick Benefit Type Factor",
            }
        )
    )

    # 10. Incidence Duration Loading
    df = assumptions_dict["Incidence_duration_loading"]
    transformed["Incidence_Duration_Loading"] = df.assign(
        **{
            "Policy Duration (Curtate Years)": lambda x: x[
                "Policy Duration (Curtate Years)"
            ].astype(str)
        }
    ).rename(
        columns={
            "Accident": "Accident Duration Factor",
            "Sickness": "Sick Duration Factor",
        }
    )

    # 11. Incidence Age Rates Sickness Combined
    df_f = assumptions_dict["Incidence_age_rates_females"][["Sex", "Age", "Sickness"]]
    df_m = assumptions_dict["Incidence_age_rates_males"][["Sex", "Age", "Sickness"]]

    df_f = df_f.rename(
        columns={"Age": "Age LB", "Sex": "sex", "Sickness": "Sick Age Rates"}
    )
    df_m = df_m.rename(
        columns={"Age": "Age LB", "Sex": "sex", "Sickness": "Sick Age Rates"}
    )

    transformed["Incidence_Age_Rates_Sickness_Combined"] = pd.concat(
        [df_m, df_f], ignore_index=True
    )

    # 12. Death Only Mortality Floor
    df = assumptions_dict["DeathOnly_mort_floor"]
    mortality_floor = df[["Age LB", "225% MS", "225% FS"]].rename(
        columns={"225% MS": "M", "225% FS": "F"}
    )
    transformed["Death_Only_Mortality_Floor"] = pd.melt(
        mortality_floor,
        id_vars=["Age LB"],
        var_name="sex",
        value_name="Mortality Floor",
    )

    # 13. Termination Age Rates
    df = assumptions_dict["Termination_age_rates"]
    termination_rates = df.rename(
        columns={
            "Age last birthday at last policy anniversary at Date of Disablement \ Gender": "Age LB",
            "Male": "M",
            "Female": "F",
        }
    )
    transformed["Termination_Age_Rates"] = pd.melt(
        termination_rates,
        id_vars=["Age LB"],
        var_name="sex",
        value_name="Termination Age Rates",
    )

    # 14. Termination Smoker
    df = assumptions_dict["Termination_smoker"]
    transformed["Termination_Smoker"] = df.rename(
        columns={"Smoker Status": "Smoker status", "Rate": "Termination Smoker status"}
    )

    # 15. Termination Benefit Type
    df = assumptions_dict["Termination_benefit_type"]
    benefit_type_mapping = {"Agreed Value": "A", "Indemnity": "I"}
    transformed["Termination_Benefit_Type"] = df.rename(
        columns={"Rates": "Termination Benefit Type"}
    ).assign(**{"Benefit Type": lambda x: x["Benefit Type"].map(benefit_type_mapping)})

    # 16. Termination Duration Factor Accident
    df = assumptions_dict["Termination_duration_factor_acc"]
    transformed["Termination_Duration_Factor_Accident"] = (
        df.rename(
            columns={
                "Curtate Policy Year": "Policy Year_10+",
                "Sex": "sex",
                "Rates": "Accident Policy Duration Factor",
            }
        )
        .drop(columns=["Type"])
        .assign(**{"Policy Year_10+": lambda x: x["Policy Year_10+"].astype(str)})
    )

    # 17. Termination Duration Claim Accident
    df = assumptions_dict["Termination_duration_claim_acc"]
    transformed["Termination_Duration_Claim_Acc"] = df.rename(
        columns={
            "Sex": "sex",
            "Waiting_period": "Waiting Period",
            "Rates": "Claim Waiting Occupation Factor",
        }
    ).assign(**{"Claim Duration": lambda x: x["Claim Duration"].astype(int)})

    # 18. Termination Benefit Period
    df = assumptions_dict["Termination_benefit_period"]
    transformed["Termination_Benefit_Period"] = df.rename(
        columns={
            "Duration since Disablement (Years***)": "Claim Duration_6+",
            "Benefit Period": "Benefit Period_65+",
            "Rates": "Benefit Period Factor",
        }
    ).assign(
        **{
            "Claim Duration_6+": lambda x: x["Claim Duration_6+"].astype(str),
            "Benefit Period_65+": lambda x: x["Benefit Period_65+"].astype(str),
        }
    )

    # 19. Termination Duration Factor Sickness
    df = assumptions_dict["Termination_duration_factor_sic"]
    transformed["Termination_Duration_Factor_Sickness"] = (
        df.rename(
            columns={
                "Curtate Policy Year": "Policy Year_10+",
                "Sex": "sex",
                "Rates": "Sickness Policy Duration Factor",
            }
        )
        .drop(columns=["Type"])
        .assign(**{"Policy Year_10+": lambda x: x["Policy Year_10+"].astype(str)})
    )

    # 20. Termination Duration Claim Sickness
    df = assumptions_dict["Termination_duration_claim_sick"]
    transformed["Termination_Duration_Claim_Sick"] = df.rename(
        columns={
            "Sex": "sex",
            "Waiting_period": "Waiting Period",
            "Rates": "Claim Waiting Occupation Factor",
        }
    ).assign(**{"Claim Duration": lambda x: x["Claim Duration"].astype(int)})

    # 21. Inflation
    df = assumptions_dict["Inflation"]
    try:
        # First try parsing with pandas default parser
        df["Date"] = pd.to_datetime(df["Year"], format="mixed", dayfirst=True)
    except Exception:
        # Fallback method if the first attempt fails
        df["Date"] = pd.to_datetime(df["Year"], format="%Y-%m-%d", errors="coerce")

    transformed["Inflation"] = df.rename(columns={"Year": "Date"})

    # 22. Forward Rate
    df = assumptions_dict["Forward_rates"]
    try:
        # First try parsing with pandas default parser
        df["Month"] = pd.to_datetime(df["Month"], format="mixed", dayfirst=True)
    except Exception:
        # Fallback method if the first attempt fails
        df["Month"] = pd.to_datetime(df["Month"], format="%Y-%m-%d", errors="coerce")

    transformed["Forward_rate"] = df

    return transformed


def update_model_spaces(Mapping_space, Assumptions_space, assumptions):
    """
    Update model spaces with transformed assumptions

    Args:
        Mapping_space: ModelX space for mapping tables
        Assumptions_space: ModelX space for assumption tables
        assumptions: Dictionary of transformed assumptions
    """
    try:
        # Update Mapping Tables
        Mapping_space.Occupation = assumptions["Occupation"]
        Mapping_space.Waiting_period = assumptions["Waiting_period"]
        Mapping_space.Smoker = assumptions["Smoker"]
        Mapping_space.Benefit_period = assumptions["Benefit_period"]
        Mapping_space.Prem_payment_freq = assumptions["Prem_payment_freq"]

        # Update Assumption Tables
        # Reference Tables
        Assumptions_space.Mortality = assumptions["Mortality"]
        Assumptions_space.Lapse = assumptions["Lapse"]
        Assumptions_space.TPD = assumptions["TPD"]
        Assumptions_space.Trauma = assumptions["Trauma"]
        Assumptions_space.Prem_Rate_Level = assumptions["Prem_Rate_Level"]
        Assumptions_space.Prem_Rate_Stepped = assumptions["Prem_Rate_Stepped"]
        Assumptions_space.Rein_Prem_Rate_Level = assumptions["Rein_Prem_Rate_Level"]
        Assumptions_space.Rein_Prem_Rate_Stepped = assumptions["Rein_Prem_Rate_Stepped"]

        # Economic Assumptions
        Assumptions_space.Mth_Discount_rate = assumptions["Mth_Discount_rate"]
        Assumptions_space.Inflation = assumptions["Inflation"]
        Assumptions_space.Forward_rate = assumptions["Forward_rate"]

        # Expense and Commission
        Assumptions_space.Commission_rate = assumptions["Commission_rate"]
        Assumptions_space.Prem_related_expenses = assumptions["Prem_related_expenses"]
        Assumptions_space.Fixed_expenses = assumptions["Fixed_expenses"]
        Assumptions_space.Risk_adj_pc = assumptions["Risk_adj_pc"]
        Assumptions_space.Valuation_Variables = assumptions["Valuation_Variables"]

        # Death Only Tables
        Assumptions_space.Death_Only_Mort_Age_Rates = assumptions[
            "Death_Only_Mort_Age_Rates"
        ]
        Assumptions_space.Death_Only_Duration_Loading = assumptions[
            "Death_Only_Duration_Loading"
        ]
        Assumptions_space.Death_Only_Mortality_Floor = assumptions[
            "Death_Only_Mortality_Floor"
        ]

        # Incidence Tables
        Assumptions_space.Incidence_Age_Rates_Female = assumptions[
            "Incidence_Age_Rates_Female"
        ]
        Assumptions_space.Incidence_Age_Rates_Male = assumptions[
            "Incidence_Age_Rates_Male"
        ]
        Assumptions_space.Incidence_Lifetime_Benefit_Period = assumptions[
            "Incidence_Lifetime_Benefit_Period"
        ]
        Assumptions_space.Incidence_Waiting_Period = assumptions[
            "Incidence_Waiting_Period"
        ]
        Assumptions_space.Incidence_Smoking_Status = assumptions[
            "Incidence_Smoking_Status"
        ]
        Assumptions_space.Incidence_Benefit_Type = assumptions["Incidence_Benefit_Type"]
        Assumptions_space.Incidence_Duration_Loading = assumptions[
            "Incidence_Duration_Loading"
        ]
        Assumptions_space.Incidence_Age_Rates_Sickness_Combined = assumptions[
            "Incidence_Age_Rates_Sickness_Combined"
        ]

        # Termination Tables
        Assumptions_space.Termination_Age_Rates = assumptions["Termination_Age_Rates"]
        Assumptions_space.Termination_Duration_Claim_Acc = assumptions[
            "Termination_Duration_Claim_Acc"
        ]
        Assumptions_space.Termination_Duration_Claim_Sick = assumptions[
            "Termination_Duration_Claim_Sick"
        ]
        Assumptions_space.Termination_Smoker = assumptions["Termination_Smoker"]
        Assumptions_space.Termination_Benefit_Type = assumptions[
            "Termination_Benefit_Type"
        ]
        Assumptions_space.Termination_Duration_Factor_Accident = assumptions[
            "Termination_Duration_Factor_Accident"
        ]
        Assumptions_space.Termination_Benefit_Period = assumptions[
            "Termination_Benefit_Period"
        ]
        Assumptions_space.Termination_Duration_Factor_Sickness = assumptions[
            "Termination_Duration_Factor_Sickness"
        ]
        Assumptions_space.Termination_New_Claim = assumptions["Termination_New_Claim"]
        Assumptions_space.Termination_Cause_Sickness = assumptions[
            "Termination_Cause_Sickness"
        ]

        print("Successfully updated all model spaces")

    except KeyError as e:
        print(f"Error: Missing assumption table: {str(e)}")
    except Exception as e:
        print(f"Error updating model spaces: {str(e)}")
