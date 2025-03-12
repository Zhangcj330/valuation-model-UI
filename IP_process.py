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
            transformed[table] = assumptions_dict[table].copy()

    # 1. Simple direct assignments (no transformations needed)
    simple_tables = [
        "Mortality",
        "Lapse",
        "TPD",
        "Trauma",
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
            transformed[table] = assumptions_dict[table].copy()

    # Premium rate tables with Y/N to S/N transformation
    premium_tables = [
        "Prem_rate_level",
        "Prem_rate_stepped",
        "Rein_Prem_rate_level",
        "Rein_Prem_rate_stepped",
    ]

    for table in premium_tables:
        if table in assumptions_dict:
            df = assumptions_dict[table].copy()
            # Only transform the 'Smoker status' column
            df["Smoker status"] = df["Smoker status"].map({"Y": "S", "N": "N"})
            transformed[table] = df

    # 2. Death Only Mortality transformations
    df_death_only_mort = assumptions_dict["DeathOnly_mort_age_rates"].copy()
    Death_Only_Mort_Age_Rates = df_death_only_mort.rename(
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
    df_death_only_duration = assumptions_dict["DeathOnly_duration_loading"].copy()
    transformed["Death_Only_Duration_Loading"] = (
        pd.melt(
            df_death_only_duration,
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
    df_incidence_female = assumptions_dict["Incidence_age_rates_females"].copy()
    transformed["Incidence_Age_Rates_Female"] = df_incidence_female.rename(
        columns={
            "Age": "Age LB",
            "Accident": "Accident Age Rates",
            "Sickness": "Sick Age Rates",
        }
    )

    # 5. Incidence Age Rates (Male)
    df_incidence_male = assumptions_dict["Incidence_age_rates_males"].copy()
    male_rates = df_incidence_male.rename(columns={"Age": "Age LB"})
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
    df_lifetime_benefit = assumptions_dict["Incidence_lifetime_bene_period"].copy()
    transformed["Incidence_Lifetime_Benefit_Period"] = df_lifetime_benefit.rename(
        columns={
            "Accident": "Accident Lifetime Factor",
            "Sickness": "Sick Lifetime Factor",
            "Sex": "sex",
        }
    )

    # 7. Incidence Waiting Period
    df_waiting_period = assumptions_dict["Incidence_waiting_period"].copy()
    occupation_mapping = {
        "Professional/Medical": "P",
        "White Collar": "W",
        "Sedentary": "S",
        "Trades-person": "T",
        "Blue/Heavy Blue Collar": "B",
    }
    waiting_period = pd.melt(
        df_waiting_period,
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
    df_smoking_status = assumptions_dict["Incidence_smoking_status"].copy()
    occupation_mapping = {
        "Combined White Collar": ["W", "P"],
        "Combined Blue Collar": ["S", "T", "B"],
    }
    smoking_mapping = {"Smoker": "S", "Non-smoker": "N"}

    smoking_status = pd.melt(
        df_smoking_status,
        id_vars=["Type", "Sex", "Smoking_Status"],
        var_name="Occupation Type",
        value_name="Smoker Factor",
    )
    smoking_status["Smoking_Status"] = smoking_status["Smoking_Status"].map(
        smoking_mapping
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
    df_benefit_type = assumptions_dict["Incidence_benefit_type"].copy()
    benefit_type_mapping = {"Agreed Value": "A", "Indemnity": "I"}

    benefit_type = pd.melt(
        df_benefit_type,
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
    df_duration_loading = assumptions_dict["Incidence_duration_loading"].copy()
    transformed["Incidence_Duration_Loading"] = df_duration_loading.assign(
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
    df_sickness_female = assumptions_dict["Incidence_age_rates_females"][
        ["Sex", "Age", "Sickness"]
    ].copy()
    df_sickness_male = assumptions_dict["Incidence_age_rates_males"][
        ["Sex", "Age", "Sickness"]
    ].copy()

    df_sickness_female = df_sickness_female.rename(
        columns={"Age": "Age LB", "Sex": "sex", "Sickness": "Sick Age Rates"}
    )
    df_sickness_male = df_sickness_male.rename(
        columns={"Age": "Age LB", "Sex": "sex", "Sickness": "Sick Age Rates"}
    )

    transformed["Incidence_Age_Rates_Sickness_Combined"] = pd.concat(
        [df_sickness_male, df_sickness_female], ignore_index=True
    )

    # 12. Death Only Mortality Floor
    df_mortality_floor = assumptions_dict["DeathOnly_mort_floor"].copy()
    mortality_floor = df_mortality_floor[["Age LB", "225% MS", "225% FS"]].rename(
        columns={"225% MS": "M", "225% FS": "F"}
    )
    transformed["Death_Only_Mortality_Floor"] = pd.melt(
        mortality_floor,
        id_vars=["Age LB"],
        var_name="sex",
        value_name="Mortality Floor",
    )

    # 13. Termination Age Rates
    df_termination_rates = assumptions_dict["Termination_age_rates"].copy()
    termination_rates = df_termination_rates.rename(
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
    df_termination_smoker = assumptions_dict["Termination_smoker"].copy()
    transformed["Termination_Smoker"] = df_termination_smoker.rename(
        columns={"Smoker Status": "Smoker status", "Rate": "Termination Smoker status"}
    )

    # 15. Termination Benefit Type
    df_termination_benefit = assumptions_dict["Termination_benefit_type"].copy()
    benefit_type_mapping = {"Agreed Value": "A", "Indemnity": "I"}
    transformed["Termination_Benefit_Type"] = df_termination_benefit.rename(
        columns={"Rates": "Termination Benefit Type"}
    ).assign(**{"Benefit Type": lambda x: x["Benefit Type"].map(benefit_type_mapping)})

    # 16. Termination Duration Factor Accident
    df_termination_duration_acc = assumptions_dict[
        "Termination_duration_factor_acc"
    ].copy()
    transformed["Termination_Duration_Factor_Accident"] = (
        df_termination_duration_acc.rename(
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
    df_termination_claim_acc = assumptions_dict["Termination_duration_claim_acc"].copy()
    transformed["Termination_Duration_Claim_Acc"] = df_termination_claim_acc.rename(
        columns={
            "Sex": "sex",
            "Waiting_period": "Waiting Period",
            "Rates": "Claim Waiting Occupation Factor",
        }
    ).assign(**{"Claim Duration": lambda x: x["Claim Duration"].astype(int)})

    # 18. Termination Benefit Period
    df_termination_benefit_period = assumptions_dict[
        "Termination_benefit_period"
    ].copy()
    transformed["Termination_Benefit_Period"] = df_termination_benefit_period.rename(
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
    df_termination_duration_sick = assumptions_dict[
        "Termination_duration_factor_sic"
    ].copy()
    transformed["Termination_Duration_Factor_Sickness"] = (
        df_termination_duration_sick.rename(
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
    df_termination_claim_sick = assumptions_dict[
        "Termination_duration_claim_sick"
    ].copy()
    transformed["Termination_Duration_Claim_Sick"] = df_termination_claim_sick.rename(
        columns={
            "Sex": "sex",
            "Waiting_period": "Waiting Period",
            "Rates": "Claim Waiting Occupation Factor",
        }
    ).assign(**{"Claim Duration": lambda x: x["Claim Duration"].astype(int)})

    # 21. Inflation
    df_inflation = assumptions_dict["Inflation"].copy()
    # 拆分年月日并重新组装
    df_inflation["Year_Year"] = df_inflation["Year"].dt.year
    df_inflation["Year_Month"] = df_inflation["Year"].dt.day
    df_inflation["Year_Day"] = df_inflation["Year"].dt.month
    df_inflation["Date"] = pd.to_datetime(
        df_inflation["Year_Year"].astype(str)
        + "-"
        + df_inflation["Year_Month"].astype(str)
        + "-"
        + df_inflation["Year_Day"].astype(str)
    ).dt.strftime("%Y-%m-%d %H:%M:%S")
    # 删除临时列
    df_inflation.drop(
        columns=["Year", "Year_Year", "Year_Month", "Year_Day"], inplace=True
    )
    transformed["Inflation"] = df_inflation

    # 21. Forward Rate
    df_forward = assumptions_dict["Forward_rates"].copy()
    # 对 Forward Rate 做同样的处理
    df_forward["Year_Year"] = df_forward["Month"].dt.year
    df_forward["Year_Month"] = df_forward["Month"].dt.day
    df_forward["Year_Day"] = df_forward["Month"].dt.month
    df_forward["Year"] = pd.to_datetime(
        df_forward["Year_Year"].astype(str)
        + "-"
        + df_forward["Year_Month"].astype(str)
        + "-"
        + df_forward["Year_Day"].astype(str)
    ).dt.strftime("%Y-%m-%d %H:%M:%S")
    # 删除临时列
    df_forward.drop(columns=["Year_Year", "Year_Month", "Year_Day"], inplace=True)
    transformed["Forward_rate"] = df_forward

    return transformed
