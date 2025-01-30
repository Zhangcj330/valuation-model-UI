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


def result_pv(t):
    """Result table of present value of cashflows

    .. seealso::

       * :func:`pv_premiums`
       * :func:`pv_claims`
       * :func:`pv_expenses`
       * :func:`pv_commissions`
       * :func:`pv_net_cf`

    """


    data = {
        "PV Premiums": pv_premiums(t),
        "PV Claims": pv_claims(t),
        "PV Expenses": pv_expenses(t),
        "PV Commissions": pv_commissions(t),
        "BEL": BEL(t),
    }

    return pd.DataFrame(data, index=Projection.model_point().index)


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


def aggregate_pvs():
    """Result table of present value

    .. seealso::

       * :func:`pv_premiums`
       * :func:`pv_claims`
       * :func:`pv_expenses`
       * :func:`pv_commissions`
       * :func:`pv_net_cf`

    """

    t_len = range(Projection.max_proj_len())

    data = {
        "Premiums": [sum(pv_premiums(t)) for t in t_len],
        "Claims": [sum(pv_claims(t)) for t in t_len],
        "Expenses": [sum(pv_expenses(t)) for t in t_len],
        "Commissions": [sum(pv_commissions(t)) for t in t_len],
    }

    return pd.DataFrame(data, index=t_len)


def aggregate_cfs():
    return Projection.result_cf()


def analytics():
    """Result table for analysis
    """

    t_len = range(Projection.max_proj_len())

    data = {
        "Premiums": [sum(Projection.premiums(t)) for t in t_len],
        "Claims": [sum(Projection.claims(t)) for t in t_len],
        "Expenses": [sum(Projection.expenses(t)) for t in t_len],
        "Commissions": [sum(Projection.commissions(t)) for t in t_len],
        "Premiums_pp": [sum(Projection.premium_pp(t)) for t in t_len],
        "Claims_pp": [sum(Projection.claim_pp(t)) for t in t_len],
        "Expenses_pp": [sum(Projection.expense_pp(t)) for t in t_len],
        "Commissions_pp": [sum(Projection.commission_pp(t)) for t in t_len],
        "pols_if": [sum(Projection.pols_if(t)) for t in t_len],
        "pols_death": [sum(Projection.pols_death(t)) for t in t_len],
        "pols_lapse": [sum(Projection.pols_lapse(t)) for t in t_len],
        "pols_maturity": [sum(Projection.pols_maturity(t)) for t in t_len],
        "PV_Premiums": [sum(pv_premiums(t)) for t in t_len],
        "PV_Claims": [sum(pv_claims(t)) for t in t_len],
        "PV_Expenses": [sum(pv_expenses(t)) for t in t_len],
        "PV_Commissions": [sum(pv_commissions(t)) for t in t_len],
    }

    return pd.DataFrame(data, index=t_len)


# ---------------------------------------------------------------------------
# References

np = ("Module", "numpy")

Projection = ("Interface", ("..", "Projection"), "auto")

pd = ("Module", "pandas")