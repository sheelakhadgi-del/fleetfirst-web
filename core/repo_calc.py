"""
Repossession gain/loss calculation and JE generation.
"""
from datetime import date
from dateutil.relativedelta import relativedelta


def months_of_depreciation(acq_date, repo_date):
    """
    Count months of depreciation per FleetFirst policy:
    - Acq date <= 15th: full month in acquisition month
    - Acq date > 15th: depreciation starts following month
    Stops at end of month prior to repo month (repo month excluded).
    """
    if acq_date.day <= 15:
        depr_start = acq_date.replace(day=1)
    else:
        depr_start = (acq_date.replace(day=1) + relativedelta(months=1))

    # Depreciation through end of month before repo month
    depr_end = repo_date.replace(day=1)

    if depr_end <= depr_start:
        return 0

    delta = relativedelta(depr_end, depr_start)
    return delta.years * 12 + delta.months


def book_value(original_cost, useful_life_months, acq_date, repo_date, residual_value=5000):
    """
    Straight-line book value of truck/asset at repo date.
    Monthly depreciation = (original_cost - residual_value) / life_months (always 60 per policy).
    """
    life = useful_life_months if useful_life_months and useful_life_months > 0 else 60
    monthly_depr = (float(original_cost) - float(residual_value)) / life
    months = months_of_depreciation(acq_date, repo_date)
    accumulated = round(monthly_depr * months, 2)
    bv = round(float(original_cost) - accumulated, 2)
    return max(bv, float(residual_value))


def calc_repo(
    original_cost,
    useful_life_months,
    acq_date,
    repo_date,
    principal_balance,
    interest_balance,
    deposit_forfeited,
    maintenance_deposit,
    asset_account="1504",
    residual_value=5000,
):
    """
    Returns a dict with all repo JE amounts.
    """
    bv = book_value(original_cost, useful_life_months, acq_date, repo_date, residual_value)
    months = months_of_depreciation(acq_date, repo_date)
    accumulated_depr = round(float(original_cost) - bv, 2)

    total_dr = round(bv + float(deposit_forfeited) + float(maintenance_deposit), 2)
    total_cr = round(float(principal_balance) + float(interest_balance), 2)
    gain_loss = round(total_cr - total_dr, 2)  # positive = gain, negative = loss

    je_lines = []

    # Debits
    je_lines.append({
        "account": f"{asset_account} {'Fixed Assets' if asset_account == '1504' else 'Right of Use Assets (Trucks)'}",
        "account_num": asset_account,
        "description": "Book Value of Truck at Repossession",
        "debit": bv,
        "credit": "",
    })
    if float(deposit_forfeited) > 0:
        je_lines.append({
            "account": "2602 Driver Truck Deposit",
            "account_num": "2602",
            "description": "Driver Deposit Forfeited",
            "debit": float(deposit_forfeited),
            "credit": "",
        })
    if float(maintenance_deposit) > 0:
        je_lines.append({
            "account": "2603 Truck Maintenance Deposit - Leasing",
            "account_num": "2603",
            "description": "Maintenance Deposit Forfeited",
            "debit": float(maintenance_deposit),
            "credit": "",
        })

    # Credits
    je_lines.append({
        "account": "1951 Lease Receivable",
        "account_num": "1951",
        "description": "Principal Balance Written Off",
        "debit": "",
        "credit": float(principal_balance),
    })
    if float(interest_balance) > 0:
        je_lines.append({
            "account": "1223 Sub-lease Interest Receivable",
            "account_num": "1223",
            "description": "Interest Receivable Written Off",
            "debit": "",
            "credit": float(interest_balance),
        })

    # Gain/Loss plug
    if gain_loss > 0:
        je_lines.append({
            "account": "7013 Gain / Loss on Repossessed Trucks Leasing",
            "account_num": "7013",
            "description": "Gain on Repossession",
            "debit": "",
            "credit": gain_loss,
        })
    elif gain_loss < 0:
        je_lines.append({
            "account": "7013 Gain / Loss on Repossessed Trucks Leasing",
            "account_num": "7013",
            "description": "Loss on Repossession",
            "debit": abs(gain_loss),
            "credit": "",
        })

    return {
        "book_value": bv,
        "accumulated_depreciation": accumulated_depr,
        "months_depreciated": months,
        "gain_loss": gain_loss,
        "je_lines": je_lines,
    }
