from modelx.serialize.jsonvalues import *

_formula = None

_bases = []

_allow_none = None

_spaces = []

# ---------------------------------------------------------------------------
# Cells

def pv_premiums(t):
    """Present value of premiums at a given time period

    .. seealso::

        * :func:`premiums`

    """

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.premiums(t+1) + pv_premiums(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def pv_dth_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.dth_claims(t) + pv_dth_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def pv_tpd_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.tpd_claims(t) + pv_tpd_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def pv_trauma_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.trauma_claims(t) + pv_trauma_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def pv_commissions(t):
    """Present value of commissions at a given time period

    .. seealso::

        * :func:`commissions`

    """

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.commissions(t+1) + pv_commissions(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def pv_expenses(t):
    """Present value of expenses at a given time period

    .. seealso::

        * :func:`expenses`

    """

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.expenses(t+1) + pv_expenses(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def pv_claims(t):
    """Present value of claims at a given time period

    .. seealso::

        * :func:`claims`

    """

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.claims(t) + pv_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def BEL(t):
    """Present value of net cashflows.

    Defined as::

        pv_premiums() - pv_claims() - pv_expenses() - pv_commissions()

    .. seealso::

        * :func:`pv_premiums`
        * :func:`pv_claims`
        * :func:`pv_expenses`
        * :func:`pv_commissions`"""

    return - pv_premiums(t) + pv_claims(t) + pv_commissions(t) + pv_expenses(t)


def pv_results(t):
    data = {
        "PV_Premiums": pv_premiums(t),
        "PV_Dth_Claims": pv_dth_claims(t),
        "PV_TPD_Claims": pv_tpd_claims(t),
        "PV_Trauma_Claims": pv_trauma_claims(t),
        "PV_Total_Claims": pv_claims(t),
        "PV Expenses": pv_expenses(t),
        "PV Commissions": pv_commissions(t),
        "BEL": BEL(t),
        "RA": RA(t),
        "I17_PV_Premiums": I17_pv_premiums(t),
        "I17_PV_Dth_Claims": I17_pv_dth_claims(t),
        "I17_PV_TPD_Claims": I17_pv_tpd_claims(t),	
        "I17_PV_Trauma_Claims": I17_pv_trauma_claims(t),	
        "I17_PV_Total_Claims": I17_pv_claims(t),
        "I17_PV_Expenses": I17_pv_expenses(t),
        "I17_PV_Commissions": I17_pv_commissions(t),	
        "I17_BEL": I17_BEL(t),
        "I17_RA": I17_RA(t),
        "I17_RI_PV_Premiums": I17_RI_pv_premiums(t),
        "I17_RI_PV_Dth_Claims": I17_RI_pv_dth_claims(t),
        "I17_RI_PV_TPD_Claims": I17_RI_pv_tpd_claims(t),	
        "I17_RI_PV_Trauma_Claims": I17_RI_pv_trauma_claims(t),	
        "I17_RI_PV_Total_Claims": I17_RI_pv_claims(t),	
        "I17_RI_BEL": I17_RI_BEL(t),
        "I17_RI_RA": I17_RI_RA(t)
    }

    return pd.DataFrame(data, index=Projection.model_point().index)


def analytics():
    """Result table for analysis
    """

    t_len = range(Projection.max_proj_len())

    data = {
        "Premiums": [sum(Projection.premiums(t)) for t in t_len],
        "Death_Claims": [sum(Projection.dth_claims(t)) for t in t_len],
        "TPD_Claims": [sum(Projection.tpd_claims(t)) for t in t_len],
        "Trauma Claims": [sum(Projection.trauma_claims(t)) for t in t_len],
        "Total Claims": [sum(Projection.claims(t)) for t in t_len],
        "Expenses": [sum(Projection.expenses(t)) for t in t_len],
        "Commissions": [sum(Projection.commissions(t)) for t in t_len],
        "Premiums_PP": [sum(Projection.premium_pp(t)) for t in t_len],
        "Death_Claim_PP": [sum(Projection.dth_claim_pp(t)) for t in t_len],
        "TPD_Claim_PP": [sum(Projection.tpd_claim_pp(t)) for t in t_len],
        "Trauma_Claim_PP": [sum(Projection.trauma_claim_pp(t)) for t in t_len],
        "Expenses_PP": [sum(Projection.expense_pp(t)) for t in t_len],
        "Commissions_PP": [sum(Projection.commission_pp(t)) for t in t_len],
        "pols_if": [sum(Projection.pols_if(t)) for t in t_len],
        "pols_death": [sum(Projection.pols_death(t)) for t in t_len],
        "pols_lapse": [sum(Projection.pols_lapse(t)) for t in t_len],
        "pols_maturity": [sum(Projection.pols_maturity(t)) for t in t_len],
        "PV_Premiums": [sum(pv_premiums(t)) for t in t_len],
        "PV_Dth_Claims": [sum(pv_dth_claims(t)) for t in t_len],
        "PV_TPD_Claims": [sum(pv_tpd_claims(t)) for t in t_len],
        "PV_Trauma_Claims": [sum(pv_trauma_claims(t)) for t in t_len],
        "PV_Total_Claims": [sum(pv_claims(t)) for t in t_len],
        "PV_Expenses": [sum(pv_expenses(t)) for t in t_len],
        "PV_Commissions": [sum(pv_commissions(t)) for t in t_len],
    }

    return pd.DataFrame(data, index=t_len)


def I17_pv_premiums(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_premiums(t+1) + I17_pv_premiums(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_pv_dth_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_dth_claims(t) + I17_pv_dth_claims(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_pv_tpd_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_tpd_claims(t) + I17_pv_tpd_claims(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_pv_trauma_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_trauma_claims(t) + I17_pv_trauma_claims(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_pv_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_claims(t) + I17_pv_claims(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_pv_expenses(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_expenses(t+1) + I17_pv_expenses(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_pv_commissions(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_commissions(t+1) + I17_pv_commissions(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_BEL(t):
    return - I17_pv_premiums(t) + I17_pv_claims(t) + I17_pv_commissions(t) + I17_pv_expenses(t)


def I17_RA(t):
    return Projection.RA_pc() * I17_pv_claims(t)


def RA(t):
    return Projection.RA_pc() * pv_claims(t)


def I17_analytics():
    """Result table for analysis
    """

    t_len = range(Projection.max_proj_len())

    data = {
        "I17_Premiums": [sum(Projection.I17_premiums(t)) for t in t_len],
        "I17_Death_Claims": [sum(Projection.I17_dth_claims(t)) for t in t_len],
        "I17_TPD_Claims": [sum(Projection.I17_tpd_claims(t)) for t in t_len],
        "I17_Trauma Claims": [sum(Projection.I17_trauma_claims(t)) for t in t_len],
        "I17_Total Claims": [sum(Projection.I17_claims(t)) for t in t_len],
        "I17_Expenses": [sum(Projection.I17_expenses(t)) for t in t_len],
        "I17_Commissions": [sum(Projection.I17_commissions(t)) for t in t_len],
        "I17_PV_Premiums": [sum(I17_pv_premiums(t)) for t in t_len],
        "I17_PV_Dth_Claims": [sum(I17_pv_dth_claims(t)) for t in t_len],
        "I17_PV_TPD_Claims": [sum(I17_pv_tpd_claims(t)) for t in t_len],
        "I17_PV_Trauma_Claims": [sum(I17_pv_trauma_claims(t)) for t in t_len],
        "I17_PV_Total_Claims": [sum(I17_pv_claims(t)) for t in t_len],
        "I17_PV_Expenses": [sum(I17_pv_expenses(t)) for t in t_len],
        "I17_PV_Commissions": [sum(I17_pv_commissions(t)) for t in t_len],
        "I17_BEL": [sum(I17_BEL(t)) for t in t_len],
        "I17_RA": [sum(I17_RA(t)) for t in t_len],
        "I17_RI_Premiums": [sum(Projection.I17_RI_premiums(t)) for t in t_len],
        "I17_RI_Death_Claims": [sum(Projection.I17_RI_dth_claims(t)) for t in t_len],
        "I17_RI_TPD_Claims": [sum(Projection.I17_RI_tpd_claims(t)) for t in t_len],
        "I17_RI_Trauma_Claims": [sum(Projection.I17_RI_trauma_claims(t)) for t in t_len],
        "I17_RI_Total_Claims": [sum(Projection.I17_RI_claims(t)) for t in t_len],
        "I17_RI_PV_Premiums": [sum(I17_RI_pv_premiums(t)) for t in t_len],
        "I17_RI_PV_Dth_Claims": [sum(I17_RI_pv_dth_claims(t)) for t in t_len],
        "I17_RI_PV_TPD_Claims": [sum(I17_RI_pv_tpd_claims(t)) for t in t_len],
        "I17_RI_PV_Trauma_Claims": [sum(I17_RI_pv_trauma_claims(t)) for t in t_len],
        "I17_RI_PV_Total_Claims": [sum(I17_RI_pv_claims(t)) for t in t_len],
        "I17_RI_BEL": [sum(I17_RI_BEL(t)) for t in t_len],
        "I17_RI_RA": [sum(I17_RI_RA(t)) for t in t_len],
    }

    return pd.DataFrame(data, index=t_len)


def RI_pv_premiums(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.RI_premiums(t+1) + RI_pv_premiums(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def RI_pv_dth_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.RI_dth_claims(t) + RI_pv_dth_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def RI_pv_tpd_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.RI_tpd_claims(t) + RI_pv_tpd_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def RI_pv_trauma_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.RI_trauma_claims(t) + RI_pv_trauma_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def RI_pv_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.RI_claims(t) + RI_pv_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def RI_BEL(t):

    return - RI_pv_premiums(t) + RI_pv_claims(t)


def I17_RI_pv_premiums(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_RI_premiums(t) + I17_RI_pv_premiums(t+1)/(1 + Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_RI_pv_dth_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_RI_dth_claims(t) + I17_RI_pv_dth_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_RI_pv_tpd_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_RI_tpd_claims(t) + I17_RI_pv_tpd_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_RI_pv_trauma_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_RI_trauma_claims(t) + I17_RI_pv_trauma_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_RI_pv_claims(t):

    if t >= (Projection.max_proj_len()-1):
        return pd.Series(0, index=Projection.model_point().index)
    else:
        result = Projection.I17_RI_claims(t) + I17_RI_pv_claims(t+1)/(1+ Projection.disc_rate_mth(t+1))
        result.index = Projection.model_point().index
        return result


def I17_RI_BEL(t):

    return I17_RI_pv_premiums(t) - I17_RI_pv_claims(t)


def I17_RI_RA(t):
    return (-Projection.RA_pc()) * I17_RI_pv_claims(t)


# ---------------------------------------------------------------------------
# References

Projection = ("Interface", ("..", "Projection"), "auto")

np = ("Module", "numpy")

pd = ("Module", "pandas")