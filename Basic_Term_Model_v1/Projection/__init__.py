"""The main Space in the :mod:`~basiclife.BasicTerm_M` model.

:mod:`~basiclife.BasicTerm_M.Projection` is the only Space defined
in the :mod:`~basiclife.BasicTerm_M` model, and it contains
all the logic and data used in the model.

.. rubric:: Parameters and References

(In all the sample code below,
the global variable ``Projection`` refers to the
:mod:`~basiclife.BasicTerm_M.Projection` Space.)

Attributes:

    model_point_table: All model point data as a DataFrame.
        The sample model point data was generated by
        *generate_model_points.ipynb* included in the library.
        By default, :func:`model_point` returns this :attr:`model_point_table`.
        The DataFrame has columns labeled ``age_at_entry``,
        ``sex``, ``policy_term``, ``policy_count``
        and ``sum_assured``.
        Cells defined in :mod:`~basiclife.BasicTerm_M.Projection`
        with the same names as these columns return
        the corresponding columns.
        (``policy_count`` is not used by default.)

        .. code-block::

            >>> Projection.model_poit_table
                       age_at_entry sex  policy_term  policy_count  sum_assured
            point_id
            1                    47   M           10             1       622000
            2                    29   M           20             1       752000
            3                    51   F           10             1       799000
            4                    32   F           20             1       422000
            5                    28   M           15             1       605000
                            ...  ..          ...           ...          ...
            9996                 47   M           20             1       827000
            9997                 30   M           15             1       826000
            9998                 45   F           20             1       783000
            9999                 39   M           20             1       302000
            10000                22   F           15             1       576000

            [10000 rows x 5 columns]

        The DataFrame is saved in the Excel file *model_point_table.xlsx*
        placed in the model folder.
        :attr:`model_point_table` is created by
        Projection's `new_pandas`_ method,
        so that the DataFrame is saved in the separate file.
        The DataFrame has the injected attribute
        of ``_mx_dataclident``::

            >>> Projection.model_point_table._mx_dataclient
            <PandasData path='model_point_table.xlsx' filetype='excel'>

        .. seealso::

           * :func:`model_point`
           * :func:`age_at_entry`
           * :func:`sex`
           * :func:`policy_term`
           * :func:`sum_assured`


    disc_rate_ann: Annual discount rates by duration as a pandas Series.

        .. code-block::

            >>> Projection.disc_rate_ann
            year
            0      0.00000
            1      0.00555
            2      0.00684
            3      0.00788
            4      0.00866

            146    0.03025
            147    0.03033
            148    0.03041
            149    0.03049
            150    0.03056
            Name: disc_rate_ann, Length: 151, dtype: float64

        The Series is saved in the Excel file *disc_rate_ann.xlsx*
        placed in the model folder.
        :attr:`disc_rate_ann` is created by
        Projection's `new_pandas`_ method,
        so that the Series is saved in the separate file.
        The Series has the injected attribute
        of ``_mx_dataclident``::

            >>> Projection.disc_rate_ann._mx_dataclient
            <PandasData path='disc_rate_ann.xlsx' filetype='excel'>

        .. seealso::

           * :func:`disc_rate_mth`
           * :func:`disc_factors`

    mort_table: Mortality table by age and duration as a DataFrame.
        See *basic_term_sample.xlsx* included in this library
        for how the sample mortality rates are created.

        .. code-block::

            >>> Projection.mort_table
                        0         1         2         3         4         5
            Age
            18   0.000231  0.000254  0.000280  0.000308  0.000338  0.000372
            19   0.000235  0.000259  0.000285  0.000313  0.000345  0.000379
            20   0.000240  0.000264  0.000290  0.000319  0.000351  0.000386
            21   0.000245  0.000269  0.000296  0.000326  0.000359  0.000394
            22   0.000250  0.000275  0.000303  0.000333  0.000367  0.000403
            ..        ...       ...       ...       ...       ...       ...
            116  1.000000  1.000000  1.000000  1.000000  1.000000  1.000000
            117  1.000000  1.000000  1.000000  1.000000  1.000000  1.000000
            118  1.000000  1.000000  1.000000  1.000000  1.000000  1.000000
            119  1.000000  1.000000  1.000000  1.000000  1.000000  1.000000
            120  1.000000  1.000000  1.000000  1.000000  1.000000  1.000000

            [103 rows x 6 columns]

        The DataFrame is saved in the Excel file *mort_table.xlsx*
        placed in the model folder.
        :attr:`mort_table` is created by
        Projection's `new_pandas`_ method,
        so that the DataFrame is saved in the separate file.
        The DataFrame has the injected attribute
        of ``_mx_dataclident``::

            >>> Projection.mort_table._mx_dataclient
            <PandasData path='mort_table.xlsx' filetype='excel'>

        .. seealso::

           * :func:`mort_rate`
           * :func:`mort_rate_mth`

    np: The `numpy`_ module.
    pd: The `pandas`_ module.

.. _numpy:
   https://numpy.org/

.. _pandas:
   https://pandas.pydata.org/

.. _new_pandas:
   https://docs.modelx.io/en/latest/reference/space/generated/modelx.core.space.UserSpace.new_pandas.html

"""

from modelx.serialize.jsonvalues import *

_formula = None

_bases = []

_allow_none = None

_spaces = []

# ---------------------------------------------------------------------------
# Cells

def age(t):
    """The attained age at time t."""
    if t == 0:
        return age_last_bday()
    else:
        check = date(t).month == date_of_birth().dt.month
        age_adj = np.where(check, 1, 0)
        result = age(t-1) + age_adj
        return result


def age_at_entry():
    """The age at entry of the model points

    """
    result = entry_date().dt.year - date_of_birth().dt.year

    check = entry_date().dt.month < date_of_birth().dt.month

    age_adj = np.where(check, -1, 0)
    result = result + age_adj

    return result


def claim_pp(t):
    """Claim per policy """

    if t == 0:
        return sum_assured()
    else:
        df = pd.concat([prem_inc_ind(), duration(t)], axis=1)
        prev_claim = claim_pp(t-1)
        conditions_met = (df['Prem_Increase_ind'] == 1) & (df['Entry date'] % 12 == 1)

        result = pd.Series(1, index=df.index)

        result[conditions_met] = 1 + inflation_rate(t)

        return prev_claim * result


def claims(t):
    """Claims

    Claims during the period from ``t`` to ``t+1`` defined as::

        claim_pp(t) * pols_death(t)

    .. seealso::

        * :func:`claim_pp`
        * :func:`pols_death`

    """
    if t == 0:
        return pd.Series(0, index= model_point().index)
    else:
        return claim_pp(t) * pols_death(t)


def commissions(t):
    if t == 0:
        return pd.Series(0, index= model_point().index)
    else:
        return  commission_pp(t) * pols_if_st(t)


def disc_factors():
    """Discount factors.

    Vector of the discount factors as a Numpy array. Used for calculating
    the present values of cashflows.

    .. seealso::

        :func:`disc_rate_mth`
    """
    return np.array(list((1 + disc_rate_mth()[t])**(-t) for t in range(max_proj_len())))


def disc_rate_mth(t):
    merged_data = pd.merge(date_proj(t), Data_Inputs.disc_curve, left_on=['Date'], right_on=['Month'], how='left')
    return merged_data.iloc[0]['Monthly forward rate']


def duration(t):
    """Duration in force in years"""
    if t == 0:
        return duration_if_st()
    else:
        return duration(t-1) + 1


def expense_acq():
    """Acquisition expense per policy

    ``300`` by default.
    """
    return 300


def expense_maint():
    """Annual maintenance expense per policy

    ``60`` by default.
    """
    return 60


def expenses(t):
    """Acquisition and maintenance expenses

    Expense cashflow during the period from ``t`` to ``t+1``.
    For any ``t``, the maintenance expense is recognized,
    which is defined as::

        pols_if(t) * expense_maint()/12 * inflation_factor(t)

    At ``t=0`` only, the acquisition expense,
    defined as :func:`expense_acq`, is recognized.

    .. seealso::

        * :func:`pols_if`
        * :func:`expense_maint`
        * :func:`inflation_factor`

    .. versionchanged:: 0.2.0
       The maintenance expense is also recognized for ``t=0``.

    """
    if t == 0:
        return pd.Series(0, index= model_point().index)
    else:
        return expense_pp(t) * pols_if_st(t)


def inflation_factor(t):
    """The inflation factor at time t

    .. seealso::

        * :func:`inflation_rate`

    """
    if t == 0: 
        return 1
    else:
        return inflation_factor(t-1)*(1 + inflation_rate(t))**(1/12)


def inflation_rate(t):
    """Inflation rate"""

    merged_data = pd.merge(date_proj(t), inflation_table(), right_on=['Year'],left_on=['Date'], how='left')
    merged_data['CPI'] = merged_data['CPI'].fillna(method='ffill')

    return merged_data.iloc[0]['CPI']


def lapse_rate(t):
    # Concatenate columns along axis=1 (side by side)
    result_df = pd.concat([product(), policy_year(t)], axis=1)
    df_renamed = result_df.rename(columns={
    'product': 'Product',
    'Entry date': 'Policy Year'})

    # Merging the DataFrames on 'Product Name' and 'Policy Year'
    merged_data = pd.merge(df_renamed, Data_Inputs.lapse_rate_table, on=['Product', 'Policy Year'], how='left')

    merged_data.index = model_point().index
    return merged_data["Lapse"]


max_proj_len = lambda: max(proj_len())
"""The max of all projection lengths

Defined as ``max(proj_len())``

.. seealso::
    :func:`proj_len`
"""

def model_point():
    """Target model points

    Returns as a DataFrame the model points to be in the scope of calculation.
    By default, this Cells returns the entire :attr:`model_point_table`
    without change.
    To select model points, change this formula so that this
    Cells returns a DataFrame that contains only the selected model points.

    Examples:
        To select only the model point 1::

            def model_point():
                return model_point_table.loc[1:1]

        To select model points whose ages at entry are 40 or greater::

            def model_point():
                return model_point_table[model_point_table["age_at_entry"] >= 40]

    Note that the shape of the returned DataFrame must be the
    same as the original DataFrame, i.e. :attr:`model_point_table`.

    When selecting only one model point, make sure the
    returned object is a DataFrame, not a Series, as seen in the example
    above where ``model_point_table.loc[1:1]`` is specified
    instead of ``model_point_table.loc[1]``.

    Be careful not to accidentally change the original table.
    """
    return Data_Inputs.model_point_table.iloc[0:1000]


def mort_rate(t):
    """Mortality rate to be applied at time t

    .. seealso::

       * :attr:`mort_table`
       * :func:`mort_rate_mth`

"""

    flattened = Data_Inputs.mort_table.melt(id_vars=["Age"], var_name="sex", value_name="mort_rate")
    df = pd.concat([age(t), sex()], axis=1)
    merged_data = pd.merge(df, flattened, left_on=['DOB', 'sex'], right_on=['Age', 'sex'], how='left')

    merged_data.index = model_point().index

    return merged_data['mort_rate']


def mort_rate_mth(t):
    """Monthly mortality rate to be applied at time t

    .. seealso::

       * :attr:`mort_table`
       * :func:`mort_rate`

    """
    return 1-(1- mort_rate(t))**(1/12)


def net_cf(t):
    """Net cashflow

    Net cashflow for the period from ``t`` to ``t+1`` defined as::

        premiums(t) - claims(t) - expenses(t) - commissions(t)

    .. seealso::

        * :func:`premiums`
        * :func:`claims`
        * :func:`expenses`
        * :func:`commissions`

    """
    return premiums(t) - claims(t) - expenses(t) - commissions(t)


def net_premium_pp():
    """Net premium per policy

    The net premium per policy is defined so that
    the present value of net premiums equates to the present value of
    claims::

        pv_claims() / pv_pols_if()

    .. seealso::

        * :func:`pv_claims`
        * :func:`pv_pols_if`

    """
    return pv_claims() / pv_pols_if()


def policy_term():
    """The policy term of the model points.

    The ``policy_term`` column of the DataFrame returned by
    :func:`model_point`.
    """
    return model_point()["policy_term"]


def pols_death(t):
    """Number of death occurring at time t"""
    if t == 0: 
        return pd.Series(0, index=Data_Inputs.model_point_table.index)
    else:
        return pols_if_st(t) * mort_rate_mth(t)


def pols_if(t):
    """Number of policies in-force

    Number of in-force policies calculated recursively.
    The initial value is read from :func:`pols_if_init`.
    Subsequent values are defined recursively as::

        pols_if(t-1) - pols_lapse(t-1) - pols_death(t-1) - pols_maturity(t)

    .. seealso::
        * :func:`pols_lapse`
        * :func:`pols_death`
        * :func:`pols_maturity`

    """
    if t==0:
        return pols_if_init()
    elif t < max_proj_len():
        return pols_if_st(t) - pols_lapse(t) - pols_death(t) 
    else:
        raise KeyError("t out of range")


def pols_if_init():
    """Initial Number of Policies In-force

    Number of in-force policies at time 0 referenced from :func:`pols_if`.
    Defaults to 1.
    """
    return pd.Series(1, index=model_point().index)


def pols_lapse(t):
    """Number of lapse occurring at time t

    .. seealso::
        * :func:`pols_if`
        * :func:`lapse_rate`

    """
    if t == 0: 
        return pd.Series(0, index=model_point().index)
    else:
        return (pols_if_st(t) - pols_death(t)) * (1-(1 - lapse_rate(t))**(1/12))


def pols_maturity(t):
    """Number of maturing policies

    The policy maturity occurs at ``t == 12 * policy_term()``,
    after death and lapse during the last period::

        pols_if(t-1) - pols_lapse(t-1) - pols_death(t-1)

    otherwise ``0``.
    """
    if t == 0: 
        return pd.Series(0, index=model_point().index)
    else: 
        check = duration(t) > policy_term() * 12
        return check * pols_if(t-1)


def premium_pp(t):

    """Monthly premium per policy
    """
    if t == 0:
        return ann_premium()
    else:
        df = pd.concat([prem_inc_ind(), duration(t)], axis=1)
        prev_premium = premium_pp(t-1)
        conditions_met = (df['Prem_Increase_ind'] == 1) & (df['Entry date'] %12 == 1)

        result = pd.Series(1.0, index=df.index)

        result[conditions_met] = 1 + inflation_rate(t)

        return prev_premium * result


def premiums(t):
    """Premium income

    Premium income during the period from ``t`` to ``t+1`` defined as::

        premium_pp(t) * pols_if(t)

    .. seealso::

        * :func:`premium_pp`
        * :func:`pols_if`

    """
    if t == 0:
        return pd.Series(0, index= model_point().index)
    else:
        return premium_pp(t) * pols_if_st(t) * prem_pay_prop(t)


def proj_len():
    """Projection length in months

    Projection length in months defined as::

        12 * policy_term() + 1

    Since this model carries out projections for all the model points
    simultaneously, the projections are actually carried out
    from 0 to :attr:`max_proj_len` for all the model points.

    .. seealso::

        :func:`policy_term`

    """
    return 12 * policy_term() + 1


def pv_claims():
    """Present value of claims

    .. seealso::

        * :func:`claims`

    """
    cl = np.array(list(claims(t) for t in range(max_proj_len()))).transpose()

    return cl @ disc_factors()[:max_proj_len()]


def pv_commissions():
    """Present value of commissions

    .. seealso::

        * :func:`expenses`

    """
    result = np.array(list(commissions(t) for t in range(max_proj_len()))).transpose()

    return result @ disc_factors()[:max_proj_len()]


def pv_expenses():
    """Present value of expenses

    .. seealso::

        * :func:`expenses`

    """
    result = np.array(list(expenses(t) for t in range(max_proj_len()))).transpose()

    return result @ disc_factors()[:max_proj_len()]


def pv_net_cf():
    """Present value of net cashflows.

    Defined as::

        pv_premiums() - pv_claims() - pv_expenses() - pv_commissions()

    .. seealso::

        * :func:`pv_premiums`
        * :func:`pv_claims`
        * :func:`pv_expenses`
        * :func:`pv_commissions`

    """
    return pv_premiums() - pv_claims() - pv_expenses() - pv_commissions()


def pv_pols_if():
    """Present value of policies in-force

    The discounted sum of the number of in-force policies at each month.
    It is used as the annuity factor for calculating :func:`net_premium_pp`.

    """
    result = np.array(list(pols_if(t) for t in range(max_proj_len()))).transpose()

    return result @ disc_factors()[:max_proj_len()]


def pv_premiums():
    """Present value of premiums

    .. seealso::

        * :func:`premiums`

    """
    result = np.array(list(premiums(t) for t in range(max_proj_len()))).transpose()

    return result @ disc_factors()[:max_proj_len()]


def result_cf():
    """Result table of cashflows

    .. seealso::

       * :func:`premiums`
       * :func:`claims`
       * :func:`expenses`
       * :func:`commissions`
       * :func:`net_cf`

    """

    t_len = range(max_proj_len())

    data = {
        "Premiums": [sum(premiums(t)) for t in t_len],
        "Claims": [sum(claims(t)) for t in t_len],
        "Expenses": [sum(expenses(t)) for t in t_len],
        "Commissions": [sum(commissions(t)) for t in t_len],
    }

    return pd.DataFrame(data, index=t_len)


def result_pv():
    """Result table of present value of cashflows

    .. seealso::

       * :func:`pv_premiums`
       * :func:`pv_claims`
       * :func:`pv_expenses`
       * :func:`pv_commissions`
       * :func:`pv_net_cf`

    """


    data = {
        "PV Premiums": pv_premiums(),
        "PV Claims": pv_claims(),
        "PV Expenses": pv_expenses(),
        "PV Commissions": pv_commissions(),
        "PV Net Cashflow": pv_net_cf()
    }

    return pd.DataFrame(data, index=model_point().index)


def sex():
    """The sex of the model points

    .. note::
       This cells is not used by default.

    The ``sex`` column of the DataFrame returned by
    :func:`model_point`.
    """
    return model_point()["sex"]


def sum_assured():
    """The sum assured of the model points

    The ``sum_assured`` column of the DataFrame returned by
    :func:`model_point`.
    """
    return model_point()["sum_assured"]


def result_pv_at_t():
    """Result table of present value of cashflows

    .. seealso::

       * :func:`pv_premiums`
       * :func:`pv_claims`
       * :func:`pv_expenses`
       * :func:`pv_commissions`
       * :func:`pv_net_cf`

    """


    data = {
        "PV Premiums": pv_premiums(),
        "PV Claims": pv_claims(),
        "PV Expenses": pv_expenses(),
        "PV Commissions": pv_commissions(),
        "PV Net Cashflow": pv_net_cf()
    }

    return pd.DataFrame(data, index=model_point().index)


def date_of_birth():
    """The date of birth of the model points

    The ``date_of_birth`` column of the DataFrame returned by
    :func:`model_point`.
    """
    return pd.to_datetime(model_point()["DOB"])


def entry_date():
    """The date of entry of the model points

    The ``entry_date`` column of the DataFrame returned by
    :func:`model_point`.
    """
    return pd.to_datetime(model_point()["Entry date"])


def duration_if_st():
    """The age at entry of the model points

    """

    result = 12 * (Data_Inputs.val_date.year - entry_date().dt.year) + Data_Inputs.val_date.month - entry_date().dt.month + 1
    return result


def age_last_bday():
    """The age at entry of the model points

    """
    result = Data_Inputs.val_date.year - date_of_birth().dt.year

    check = Data_Inputs.val_date.month < date_of_birth().dt.month

    age_adj = np.where(check, -1, 0)
    result = result + age_adj

    return result


def policy_year(t):

    result = duration(t)/12
    return np.ceil(result)


def product():
    """product name for valuation"""

    return (model_point()["Product"])


def prem_inc_ind():
    """product name for valuation"""

    return (model_point()["Prem_Increase_ind"])


def ann_premium():
    """product name for valuation"""

    return (model_point()["Annual Prem"])


def date_proj(t):
    # Generate dates using a list comprehension
    dates = [date(t) + pd.DateOffset(months=i) for i in range(max_proj_len())]

    # Convert the list of dates into a pandas DataFrame
    df = pd.DataFrame(dates, columns=['Date'])
    df ['Date'] = pd.to_datetime(df['Date'])
    df['Date'] = df['Date'].dt.to_period('M').dt.to_timestamp()
    return df


def date(t):

    if t == 0:
        return Data_Inputs.val_date
    else:
        return date(t-1) + pd.DateOffset(months=1)


def prem_freq():
    """product name for valuation"""

    return (model_point()["prem _freq"])


def inflation_table():
    inflation_table = Data_Inputs.inflation_rate_table.dropna(subset=['CPI'])
    inflation_table['Year'] = pd.to_datetime(inflation_table['Year'])

    return inflation_table


def prem_pay_prop(t):
        """assuming monthly frequency
        df_new = pd.DataFrame(1/12, index=model_point().index, columns=['prem_pay_prop'])
        return df_new['prem_pay_prop']"""
        prem_freq = model_point()["Prem Freq"]
        df = pd.concat([prem_freq, duration(t)], axis=1)

        check = (df["Prem Freq"] == 12) | (df["Entry date"]%(12/df["Prem Freq"]) == 1)

        adj = np.where(check, 1/df["Prem Freq"], 0)

        return pd.Series(adj, index= model_point().index)


def prem_exp_pc(t):
    # Concatenate columns along axis=1 (side by side)
    result_df = pd.concat([product(), policy_year(t)], axis=1)
    df_renamed = result_df.rename(columns={'Product': 'Product','Entry date': 'Policy Year'})

    # Merging the DataFrames on 'Product Name' and 'Policy Year'
    merged_data = pd.merge(df_renamed, Data_Inputs.prem_exp_table, on=['Product', 'Policy Year'], how='left')
    merged_data.index = model_point().index
    return merged_data["%"]


def fixed_exp(t):
    # Concatenate columns along axis=1 (side by side)
    result_df = pd.concat([product(), policy_year(t)], axis=1)
    df_renamed = result_df.rename(columns={'Product': 'Product','Entry date': 'Policy Year'})

    # Merging the DataFrames on 'Product Name' and 'Policy Year'
    merged_data = pd.merge(df_renamed, Data_Inputs.fixed_exp_table, on=['Product', 'Policy Year'], how='left')
    merged_data.index = model_point().index
    return merged_data["$"]


def comm_pc(t):
    # Concatenate columns along axis=1 (side by side)
    result_df = pd.concat([product(), policy_year(t)], axis=1)
    df_renamed = result_df.rename(columns={'Product': 'Product','Entry date': 'Policy Year'})

    # Merging the DataFrames on 'Product Name' and 'Policy Year'
    merged_data = pd.merge(df_renamed, Data_Inputs.comm_table, on=['Product', 'Policy Year'], how='left')
    merged_data.index = model_point().index
    return merged_data["%"]


def expense_pp(t):
    """Acquisition and maintenance expenses

    Expense cashflow during the period from ``t`` to ``t+1``.
    For any ``t``, the maintenance expense is recognized,
    which is defined as::

        pols_if(t) * expense_maint()/12 * inflation_factor(t)

    At ``t=0`` only, the acquisition expense,
    defined as :func:`expense_acq`, is recognized.

    .. seealso::

        * :func:`pols_if`
        * :func:`expense_maint`
        * :func:`inflation_factor`

    .. versionchanged:: 0.2.0
       The maintenance expense is also recognized for ``t=0``.

    """
    if t == 0:
        return pd.Series(0, index= model_point().index)
    else:
        return  (premium_pp(t) * prem_exp_pc(t) * prem_pay_prop(t) + (fixed_exp(t)/12) * inflation_factor(t))


def commission_pp(t):
    if t == 0:
        return pd.Series(0, index= model_point().index)
    else:
        return  (premium_pp(t) * comm_pc(t) * prem_pay_prop(t))


def pols_if_st(t):
    if t ==0: 
        return pd.Series(0, index=model_point().index) 
    else: 
        return pols_if(t-1) - pols_maturity(t)


# ---------------------------------------------------------------------------
# References

np = ("Module", "numpy")

pd = ("Module", "pandas")

Data_Inputs = ("Interface", ("..", "Data_Inputs"), "auto")