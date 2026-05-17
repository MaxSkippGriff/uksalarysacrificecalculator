"""UK Salary Sacrifice Calculator — 2026/27 tax year constants and logic."""

from __future__ import annotations
import datetime
from dataclasses import dataclass
from typing import Literal


def active_tax_year() -> str:
    today = datetime.date.today()
    return "2026/27" if today >= datetime.date(2026, 4, 6) else "2025/26"


TAX_YEAR = "2026/27"

# Income tax thresholds 2026/27 (England, Wales, NI)
PERSONAL_ALLOWANCE = 12_570
BASIC_RATE_LIMIT = 50_270
HIGHER_RATE_LIMIT = 125_140
BASIC_RATE = 0.20
HIGHER_RATE = 0.40
ADDITIONAL_RATE = 0.45

# Scottish income tax 2026/27 — TAXABLE income upper thresholds (after PA deduction).
# starter £0–£3,967 / basic £3,968–£16,956 / intermediate £16,957–£31,092 /
# higher £31,093–£62,430 / advanced £62,431–£125,140 / top above £125,140
# Source: https://www.gov.uk/government/publications/rates-and-allowances-income-tax
SCOTTISH_BANDS = [
    (3_967, 0.19),     # Starter — 2026/27
    (16_956, 0.20),    # Basic — 2026/27
    (31_092, 0.21),    # Intermediate — 2026/27
    (62_430, 0.42),    # Higher — 2026/27
    (125_140, 0.45),   # Advanced — 2026/27
    (float('inf'), 0.48),  # Top — 2026/27
]

# Employee NI 2026/27
EMPLOYEE_NI_THRESHOLD = 12_570
EMPLOYEE_NI_UPPER = 50_270
EMPLOYEE_NI_RATE_1 = 0.08   # 8% on £12,570–£50,270
EMPLOYEE_NI_RATE_2 = 0.02   # 2% above £50,270

# Employer NI 2026/27
EMPLOYER_NI_THRESHOLD = 5_000
EMPLOYER_NI_RATE = 0.15

# Student loan thresholds 2026/27 (estimated)
STUDENT_LOAN_PLAN1 = 24_990
STUDENT_LOAN_PLAN2 = 27_295
STUDENT_LOAN_PLAN4 = 31_395  # Scotland
STUDENT_LOAN_POSTGRAD = 21_000
STUDENT_LOAN_RATE_UG = 0.09
STUDENT_LOAN_RATE_PG = 0.06


@dataclass(frozen=True)
class TakeHomeResult:
    gross_salary: float
    income_tax: float
    employee_ni: float
    student_loan: float
    total_deductions: float
    take_home_annual: float
    take_home_monthly: float


@dataclass(frozen=True)
class SalarySacrificeResult:
    # Before sacrifice
    before: TakeHomeResult
    # After sacrifice
    after: TakeHomeResult
    sacrifice_amount: float
    pension_or_benefit_value: float
    income_tax_saving: float
    employee_ni_saving: float
    employer_ni_saving: float
    student_loan_change: float
    net_monthly_cost: float
    effective_saving_annual: float
    effective_saving_pct: float
    sacrifice_type: str


def _r(v: float) -> float:
    return round(float(v), 2)


def _income_tax_england(gross: float) -> float:
    """Income tax for England/Wales/NI."""
    pa = PERSONAL_ALLOWANCE
    if gross > 100_000:
        pa = max(0.0, PERSONAL_ALLOWANCE - (gross - 100_000) / 2.0)
    taxable = max(0.0, gross - pa)
    if taxable <= 0:
        return 0.0
    basic_band = BASIC_RATE_LIMIT - PERSONAL_ALLOWANCE  # 37700
    if taxable <= basic_band:
        return taxable * BASIC_RATE
    elif gross <= HIGHER_RATE_LIMIT:
        return basic_band * BASIC_RATE + (taxable - basic_band) * HIGHER_RATE
    else:
        higher_band = HIGHER_RATE_LIMIT - BASIC_RATE_LIMIT  # 74870
        return basic_band * BASIC_RATE + higher_band * HIGHER_RATE + (taxable - basic_band - higher_band) * ADDITIONAL_RATE


def _income_tax_scotland(gross: float) -> float:
    """Income tax for Scotland (estimated 2026/27 rates)."""
    pa = PERSONAL_ALLOWANCE
    if gross > 100_000:
        pa = max(0.0, PERSONAL_ALLOWANCE - (gross - 100_000) / 2.0)
    taxable = max(0.0, gross - pa)
    if taxable <= 0:
        return 0.0
    tax = 0.0
    prev = 0.0
    for upper, rate in SCOTTISH_BANDS:
        band = max(0.0, min(taxable, upper) - prev)
        tax += band * rate
        prev = upper
        if taxable <= upper:
            break
    return tax


def _employee_ni(gross: float) -> float:
    """Employee Class 1 NI for 2026/27."""
    if gross <= EMPLOYEE_NI_THRESHOLD:
        return 0.0
    elif gross <= EMPLOYEE_NI_UPPER:
        return (gross - EMPLOYEE_NI_THRESHOLD) * EMPLOYEE_NI_RATE_1
    else:
        return ((EMPLOYEE_NI_UPPER - EMPLOYEE_NI_THRESHOLD) * EMPLOYEE_NI_RATE_1
                + (gross - EMPLOYEE_NI_UPPER) * EMPLOYEE_NI_RATE_2)


def _student_loan(gross: float, plan: str) -> float:
    """Student loan repayment."""
    thresholds = {
        "plan1": STUDENT_LOAN_PLAN1,
        "plan2": STUDENT_LOAN_PLAN2,
        "plan4": STUDENT_LOAN_PLAN4,
        "postgrad": STUDENT_LOAN_POSTGRAD,
        "none": 0,
    }
    threshold = thresholds.get(plan, 0)
    if not threshold or gross <= threshold:
        return 0.0
    rate = STUDENT_LOAN_RATE_PG if plan == "postgrad" else STUDENT_LOAN_RATE_UG
    return max(0.0, (gross - threshold) * rate)


def _take_home(gross: float, region: str, student_loan_plan: str) -> TakeHomeResult:
    if region == "scotland":
        tax = _income_tax_scotland(gross)
    else:
        tax = _income_tax_england(gross)
    ni = _employee_ni(gross)
    sl = _student_loan(gross, student_loan_plan)
    deductions = tax + ni + sl
    take_home = max(0.0, gross - deductions)
    return TakeHomeResult(
        gross_salary=_r(gross),
        income_tax=_r(tax),
        employee_ni=_r(ni),
        student_loan=_r(sl),
        total_deductions=_r(deductions),
        take_home_annual=_r(take_home),
        take_home_monthly=_r(take_home / 12.0),
    )


def calculate_salary_sacrifice(
    gross_salary: float,
    sacrifice_amount: float,
    sacrifice_type: Literal["pension", "cycle_to_work", "ev_car", "other"] = "pension",
    region: Literal["england_wales_ni", "scotland"] = "england_wales_ni",
    student_loan_plan: str = "none",
) -> SalarySacrificeResult:
    """
    Calculate take-home pay before and after salary sacrifice for 2026/27.
    sacrifice_amount: annual gross amount sacrificed.
    """
    gross = max(0.0, float(gross_salary))
    sacrifice = max(0.0, min(float(sacrifice_amount), gross))

    reduced_salary = gross - sacrifice

    before = _take_home(gross, region, student_loan_plan)
    after = _take_home(reduced_salary, region, student_loan_plan)

    income_tax_saving = _r(before.income_tax - after.income_tax)
    employee_ni_saving = _r(before.employee_ni - after.employee_ni)
    employer_ni_saving = _r(_employee_ni(gross) * 0 + max(0.0, (gross - EMPLOYER_NI_THRESHOLD) * EMPLOYER_NI_RATE - max(0.0, (reduced_salary - EMPLOYER_NI_THRESHOLD)) * EMPLOYER_NI_RATE))
    # Simplified employer NI saving
    employer_ni_saving = _r(sacrifice * EMPLOYER_NI_RATE)  # approximate

    student_loan_change = _r(after.student_loan - before.student_loan)  # negative = saving

    # Net monthly cost: take-home reduction minus tax/NI savings benefit
    # The pension/benefit has a value equal to the gross sacrifice
    take_home_reduction = _r(before.take_home_annual - after.take_home_annual)
    net_monthly_cost = _r(take_home_reduction / 12.0)

    effective_saving = _r(income_tax_saving + employee_ni_saving - abs(student_loan_change))
    effective_saving_pct = _r(effective_saving / sacrifice * 100.0) if sacrifice > 0 else 0.0

    return SalarySacrificeResult(
        before=before,
        after=after,
        sacrifice_amount=_r(sacrifice),
        pension_or_benefit_value=_r(sacrifice),
        income_tax_saving=income_tax_saving,
        employee_ni_saving=employee_ni_saving,
        employer_ni_saving=employer_ni_saving,
        student_loan_change=student_loan_change,
        net_monthly_cost=net_monthly_cost,
        effective_saving_annual=effective_saving,
        effective_saving_pct=effective_saving_pct,
        sacrifice_type=sacrifice_type,
    )
