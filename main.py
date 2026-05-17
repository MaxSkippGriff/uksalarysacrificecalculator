"""UKSalarySacrificeCalculator.co.uk Flask application."""

from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, abort, make_response, redirect, render_template, request, send_from_directory
from flask_limiter import Limiter
from scraper_guard import init_guard

from calculator import (
    active_tax_year,
    TAX_YEAR,
    calculate_salary_sacrifice,
    PERSONAL_ALLOWANCE,
    BASIC_RATE_LIMIT,
    HIGHER_RATE_LIMIT,
    EMPLOYEE_NI_THRESHOLD,
    EMPLOYEE_NI_UPPER,
)

load_dotenv()

_PUBLIC_PATHS = (
    "/sitemap.xml", "/robots.txt", "/ads.txt", "/favicon.ico",
    "/favicon-16x16.png", "/favicon-32x32.png", "/apple-touch-icon.png",
    "/site.webmanifest", "/health",
)
_HONEYPOT_BLOCKED: set = set()

app = Flask(__name__)

CANONICAL_HOST = os.getenv("CANONICAL_HOST", "uksalarysacrificecalculator.co.uk").replace("https://", "").replace("http://", "")
CANONICAL_HOST = CANONICAL_HOST[4:] if CANONICAL_HOST.startswith("www.") else CANONICAL_HOST
SITE_URL = f"https://{CANONICAL_HOST}"
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "G-JJ0RD1KNFR").strip()
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "ca-pub-3932111812673824").strip()

limiter = Limiter(
    app=app,
    key_func=lambda: (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or ""),
    default_limits=["300 per minute"],
    storage_uri="memory://",
    strategy="fixed-window",
)

init_guard(app, _PUBLIC_PATHS, "/trap", _HONEYPOT_BLOCKED)


@app.before_request
def enforce_canonical_host():
    host = (request.host or "").split(":")[0].lower()
    if not host:
        return None
    if host == f"www.{CANONICAL_HOST}":
        target = f"{SITE_URL}{request.full_path if request.query_string else request.path}"
        if target.endswith("?"):
            target = target[:-1]
        return redirect(target, code=301)
    return None


@app.after_request
def apply_cache_headers(response):
    path = request.path or ""
    if path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=300"
    elif path in ("/favicon.ico", "/site.webmanifest", "/apple-touch-icon.png", "/favicon-32x32.png", "/favicon-16x16.png"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path == "/robots.txt":
        response.headers["Cache-Control"] = "public, max-age=60"
    elif response.mimetype == "text/html":
        response.headers["Cache-Control"] = "private, no-store, max-age=0, must-revalidate"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


def _ctx(**kwargs):
    return dict(
        site_url=SITE_URL,
        tax_year=active_tax_year(),
        now=datetime.utcnow(),
        ga_measurement_id=GA_MEASUREMENT_ID,
        adsense_client=ADSENSE_CLIENT,
        **kwargs,
    )


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/favicon-32x32.png")
def favicon_32():
    return send_from_directory(app.static_folder, "favicon-32x32.png", mimetype="image/png")

@app.route("/favicon-16x16.png")
def favicon_16():
    return send_from_directory(app.static_folder, "favicon-16x16.png", mimetype="image/png")

@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    return send_from_directory(app.static_folder, "apple-touch-icon.png", mimetype="image/png")

@app.route("/site.webmanifest")
def webmanifest():
    return send_from_directory(app.static_folder, "site.webmanifest", mimetype="application/manifest+json")

@app.route("/trap")
def trap():
    xff = request.headers.get("X-Forwarded-For", "")
    _HONEYPOT_BLOCKED.add(xff.split(",")[0].strip() if xff else (request.remote_addr or ""))
    abort(403)

@app.route("/health")
def health():
    return {"status": "ok"}, 200

@app.route("/robots.txt")
def robots():
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /trap",
        "Disallow: /api/",
        "Disallow: /admin/",
        "",
        f"Sitemap: {SITE_URL}/sitemap.xml",
    ])
    r = make_response(body)
    r.content_type = "text/plain"
    return r

@app.route("/sitemap.xml")
def sitemap():
    now = datetime.utcnow().strftime("%Y-%m-%d")
    url_entries = [
        (f"{SITE_URL}/", "1.0", "weekly"),
        (f"{SITE_URL}/calculator", "0.9", "weekly"),
        (f"{SITE_URL}/methodology", "0.7", "monthly"),
        (f"{SITE_URL}/about", "0.5", "monthly"),
        (f"{SITE_URL}/privacy", "0.3", "yearly"),
        (f"{SITE_URL}/contact", "0.3", "yearly"),
        (f"{SITE_URL}/disclaimer", "0.3", "yearly"),
        (f"{SITE_URL}/salary-sacrifice-employer-ni-saving", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-electric-car", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-cycle-to-work", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-minimum-wage", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-vs-normal-pension", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-bonus", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-scotland", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-childcare", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-maternity-pay", "0.6", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-disadvantages", "0.6", "monthly"),
        (f"{SITE_URL}/guides", "0.6", "monthly"),
        (f"{SITE_URL}/calculators", "0.6", "monthly"),
        (f"{SITE_URL}/pension-salary-sacrifice-calculator", "0.7", "monthly"),
        (f"{SITE_URL}/bonus-sacrifice-calculator", "0.7", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-100k-calculator", "0.7", "monthly"),
        (f"{SITE_URL}/employer-ni-saving-calculator", "0.7", "monthly"),
    ] + [(f"{SITE_URL}/salary-sacrifice/{s}", "0.5", "monthly") for s in SACRIFICE_SALARY_AMOUNTS]
    resp = make_response(render_template("sitemap.xml", url_entries=url_entries, now=now))
    resp.content_type = "application/xml"
    return resp


@app.route("/")
def landing():
    canonical_url = SITE_URL + "/"
    calc = calculate_salary_sacrifice(60_000, 5_000, "pension", "england_wales_ni", "none")
    faq_items = [
        {
            "q": "What is salary sacrifice?",
            "a": "Salary sacrifice is a HMRC-approved arrangement where you give up part of your gross salary in exchange for a non-cash benefit — typically pension contributions, a cycle-to-work scheme or an EV company car. Because your gross salary is reduced, you pay less income tax and National Insurance."
        },
        {
            "q": "How much National Insurance do I save with salary sacrifice?",
            "a": "Employee NI for 2026/27 is 8% on earnings between £12,570 and £50,270, and 2% above that. So if your salary sits in the 8% band, each £1,000 of salary sacrifice saves you £80 in NI alone, plus income tax relief on top."
        },
        {
            "q": "Does salary sacrifice affect my state pension?",
            "a": "If your post-sacrifice salary falls below the Lower Earnings Limit (£6,396 for 2026/27), it can affect your state pension entitlement. Most people's sacrificed salary stays well above this, but it's worth checking if you sacrifice a large amount."
        },
        {
            "q": "Is salary sacrifice different for Scottish taxpayers?",
            "a": "The NI saving is the same UK-wide. Income tax savings differ because Scotland has its own bands — the intermediate rate is 21% and the higher rate starts at a different point. Our calculator lets you select Scottish rates."
        },
        {
            "q": "Can my employer pass on their NI saving to me?",
            "a": "Employers save 15% employer NI on the sacrificed amount. Some employers pass part or all of this saving back as an extra employer pension contribution. Our calculator shows the employer NI saving separately."
        },
        {
            "q": "What EV benefit-in-kind rate applies for 2026/27?",
            "a": "For 2026/27 the benefit-in-kind rate on fully electric vehicles is 4%, rising to 5% in 2027/28. This affects the taxable benefit value when using salary sacrifice for an EV company car. Our calculator highlights this where relevant."
        },
    ]
    return render_template(
        "landing.html",
        **_ctx(
            title="Salary Sacrifice Calculator UK 2026/27 | Estimate Tax, NI & Take-Home Impact",
            meta_description="Calculate the 2026/27 tax, National Insurance and take-home impact of salary sacrifice for pensions, cycle to work, EV cars and other schemes.",
            canonical_url=canonical_url,
            calc=calc,
            faq_items=faq_items,
            breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}],
        ),
    )


@app.route("/calculator")
def calculator_page():
    canonical_url = SITE_URL + "/calculator"
    return render_template(
        "calculator.html",
        **_ctx(
            title="Salary Sacrifice Calculator 2026/27 | UK Tax and NI Saving Breakdown",
            meta_description="Free UK salary sacrifice calculator for 2026/27. Enter salary, sacrifice amount and scheme type to see your income tax saving, NI saving and net monthly cost.",
            canonical_url=canonical_url,
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "Calculator", "url": canonical_url},
            ],
        ),
    )


@app.route("/methodology")
def methodology():
    canonical_url = SITE_URL + "/methodology"
    return render_template(
        "methodology.html",
        **_ctx(
            title="Methodology — How We Calculate Salary Sacrifice Savings (2026/27)",
            meta_description="How UKSalarySacrificeCalculator.co.uk calculates salary sacrifice tax and NI savings: 2026/27 rates, Scottish bands, PA tapering and what we don't model.",
            canonical_url=canonical_url,
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "Methodology", "url": canonical_url},
            ],
        ),
    )


@app.route("/about")
def about():
    canonical_url = SITE_URL + "/about"
    return render_template(
        "about.html",
        **_ctx(
            title="About UK Salary Sacrifice Calculator — Free Tool for Employees",
            meta_description="About UKSalarySacrificeCalculator.co.uk — a free, independent tool to estimate salary sacrifice tax and NI savings for 2026/27.",
            canonical_url=canonical_url,
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "About", "url": canonical_url},
            ],
        ),
    )


@app.route("/privacy")
def privacy():
    canonical_url = SITE_URL + "/privacy"
    return render_template(
        "privacy.html",
        **_ctx(
            title="Privacy Policy — UKSalarySacrificeCalculator.co.uk",
            meta_description="Privacy policy for UKSalarySacrificeCalculator.co.uk. We don't store your financial data.",
            canonical_url=canonical_url,
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "Privacy", "url": canonical_url},
            ],
        ),
    )


@app.route("/contact")
def contact():
    canonical_url = SITE_URL + "/contact"
    return render_template(
        "contact.html",
        **_ctx(
            title="Contact — UKSalarySacrificeCalculator.co.uk",
            meta_description="Get in touch with UKSalarySacrificeCalculator.co.uk.",
            canonical_url=canonical_url,
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "Contact", "url": canonical_url},
            ],
        ),
    )


@app.route("/disclaimer")
def disclaimer():
    canonical_url = SITE_URL + "/disclaimer"
    return render_template(
        "disclaimer.html",
        **_ctx(
            title="Disclaimer — UKSalarySacrificeCalculator.co.uk",
            meta_description="Disclaimer for UKSalarySacrificeCalculator.co.uk. All results are estimates only and not financial or tax advice.",
            canonical_url=canonical_url,
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "Disclaimer", "url": canonical_url},
            ],
        ),
    )


@app.route("/salary-sacrifice-employer-ni-saving")
def guide_employer_ni():
    return render_template("salary-sacrifice-employer-ni-saving.html", **_ctx(
        title="Salary Sacrifice Employer NI Saving 2026/27 | UK Guide",
        meta_description="Learn how employer National Insurance savings can arise under salary sacrifice and why employers may or may not pass them on.",
        canonical_url=SITE_URL + "/salary-sacrifice-employer-ni-saving",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Employer NI Saving", "url": SITE_URL + "/salary-sacrifice-employer-ni-saving"}],
    ))


@app.route("/salary-sacrifice-electric-car")
def guide_electric_car():
    return render_template("salary-sacrifice-electric-car.html", **_ctx(
        title="Salary Sacrifice Electric Car 2026/27 | UK Guide",
        meta_description="Understand how electric car salary sacrifice can affect take-home pay, Benefit in Kind tax and National Insurance in 2026/27.",
        canonical_url=SITE_URL + "/salary-sacrifice-electric-car",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Electric Car", "url": SITE_URL + "/salary-sacrifice-electric-car"}],
    ))


@app.route("/salary-sacrifice-cycle-to-work")
def guide_cycle_to_work():
    return render_template("salary-sacrifice-cycle-to-work.html", **_ctx(
        title="Salary Sacrifice Cycle to Work 2026/27 | UK Guide",
        meta_description="Learn how cycle to work salary sacrifice can affect pay, tax and National Insurance, with key limitations and examples.",
        canonical_url=SITE_URL + "/salary-sacrifice-cycle-to-work",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Cycle to Work", "url": SITE_URL + "/salary-sacrifice-cycle-to-work"}],
    ))


@app.route("/salary-sacrifice-minimum-wage")
def guide_minimum_wage():
    return render_template("salary-sacrifice-minimum-wage.html", **_ctx(
        title="Salary Sacrifice and Minimum Wage 2026/27 | UK Guide",
        meta_description="Understand why salary sacrifice must not reduce cash pay below National Minimum Wage and what employees should check.",
        canonical_url=SITE_URL + "/salary-sacrifice-minimum-wage",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Minimum Wage", "url": SITE_URL + "/salary-sacrifice-minimum-wage"}],
    ))


@app.route("/salary-sacrifice-vs-normal-pension")
def guide_vs_normal_pension():
    return render_template("salary-sacrifice-vs-normal-pension.html", **_ctx(
        title="Salary Sacrifice vs Normal Pension Contributions 2026/27",
        meta_description="Compare salary sacrifice and normal pension contributions, including tax relief, National Insurance and scheme differences.",
        canonical_url=SITE_URL + "/salary-sacrifice-vs-normal-pension",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Salary Sacrifice vs Normal Pension", "url": SITE_URL + "/salary-sacrifice-vs-normal-pension"}],
    ))


@app.route("/salary-sacrifice-bonus")
def guide_bonus():
    return render_template("salary-sacrifice-bonus.html", **_ctx(
        title="Salary Sacrifice on a Bonus 2026/27 | UK Guide",
        meta_description="Can you sacrifice a bonus into a pension? Learn the HMRC timing rules, the pre-bonus election window and the tax saving for higher-rate taxpayers in 2026/27.",
        canonical_url=SITE_URL + "/salary-sacrifice-bonus",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Salary Sacrifice on a Bonus", "url": SITE_URL + "/salary-sacrifice-bonus"}],
    ))


@app.route("/salary-sacrifice-scotland")
def guide_scotland():
    return render_template("salary-sacrifice-scotland.html", **_ctx(
        title="Salary Sacrifice in Scotland 2026/27 | UK Guide",
        meta_description="How salary sacrifice works for Scottish taxpayers in 2026/27 — Scottish income tax rates, intermediate and higher rate thresholds, and NI savings.",
        canonical_url=SITE_URL + "/salary-sacrifice-scotland",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Salary Sacrifice in Scotland", "url": SITE_URL + "/salary-sacrifice-scotland"}],
    ))


@app.route("/salary-sacrifice-childcare")
def guide_childcare():
    return render_template("salary-sacrifice-childcare.html", **_ctx(
        title="Salary Sacrifice for Childcare 2026/27 | UK Guide",
        meta_description="Childcare vouchers vs Tax-Free Childcare in 2026/27 — what salary sacrifice options are available, who qualifies and how much you can save.",
        canonical_url=SITE_URL + "/salary-sacrifice-childcare",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Salary Sacrifice for Childcare", "url": SITE_URL + "/salary-sacrifice-childcare"}],
    ))


@app.route("/salary-sacrifice-maternity-pay")
def guide_maternity_pay():
    return render_template("salary-sacrifice-maternity-pay.html", **_ctx(
        title="Salary Sacrifice During Maternity Leave 2026/27 | UK Guide",
        meta_description="Does salary sacrifice affect maternity pay? Understand employer pension duties, SMP calculations and what happens to your sacrifice during maternity leave in 2026/27.",
        canonical_url=SITE_URL + "/salary-sacrifice-maternity-pay",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Salary Sacrifice and Maternity Pay", "url": SITE_URL + "/salary-sacrifice-maternity-pay"}],
    ))


@app.route("/salary-sacrifice-disadvantages")
def guide_disadvantages():
    return render_template("salary-sacrifice-disadvantages.html", **_ctx(
        title="Disadvantages of Salary Sacrifice 2026/27 | UK Guide",
        meta_description="The downsides of salary sacrifice in 2026/27 — mortgage affordability, state pension, defined benefit schemes, death-in-service and minimum wage considerations.",
        canonical_url=SITE_URL + "/salary-sacrifice-disadvantages",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Disadvantages of Salary Sacrifice", "url": SITE_URL + "/salary-sacrifice-disadvantages"}],
    ))


@app.route("/guides")
def guides_index():
    return render_template("guides.html", **_ctx(
        title="Salary Sacrifice Guides 2026/27 | UKSalarySacrificeCalculator.co.uk",
        meta_description="In-depth UK salary sacrifice guides covering pensions, electric cars, cycle to work, Scotland and more.",
        canonical_url=SITE_URL + "/guides",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Guides", "url": SITE_URL + "/guides"}],
    ))


@app.route("/calculators")
def calculators_index():
    return render_template("calculators.html", **_ctx(
        title="Salary Sacrifice Calculators 2026/27 | UKSalarySacrificeCalculator.co.uk",
        meta_description="Free UK salary sacrifice calculators for pensions, bonuses, the £100k tax trap and employer NI savings.",
        canonical_url=SITE_URL + "/calculators",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Calculators", "url": SITE_URL + "/calculators"}],
    ))


@app.route("/pension-salary-sacrifice-calculator")
def pension_salary_sacrifice_calculator():
    return render_template("pension-salary-sacrifice-calculator.html", **_ctx(
        title="Pension Salary Sacrifice Calculator 2026/27 | UKSalarySacrificeCalculator.co.uk",
        meta_description="Estimate income tax and NI savings from pension salary sacrifice in 2026/27, including employer NI passthrough.",
        canonical_url=SITE_URL + "/pension-salary-sacrifice-calculator",
        breadcrumbs=[
            {"name": "Home", "url": SITE_URL + "/"},
            {"name": "Calculators", "url": SITE_URL + "/calculators"},
            {"name": "Pension Salary Sacrifice Calculator", "url": SITE_URL + "/pension-salary-sacrifice-calculator"},
        ],
    ))


@app.route("/bonus-sacrifice-calculator")
def bonus_sacrifice_calculator():
    return render_template("bonus-sacrifice-calculator.html", **_ctx(
        title="Bonus Sacrifice Calculator 2026/27 | UKSalarySacrificeCalculator.co.uk",
        meta_description="Estimate the tax saving from sacrificing a bonus into pension instead of taking it as cash in 2026/27.",
        canonical_url=SITE_URL + "/bonus-sacrifice-calculator",
        breadcrumbs=[
            {"name": "Home", "url": SITE_URL + "/"},
            {"name": "Calculators", "url": SITE_URL + "/calculators"},
            {"name": "Bonus Sacrifice Calculator", "url": SITE_URL + "/bonus-sacrifice-calculator"},
        ],
    ))


@app.route("/salary-sacrifice-100k-calculator")
def salary_sacrifice_100k_calculator():
    return render_template("salary-sacrifice-100k-calculator.html", **_ctx(
        title="£100k Tax Trap Salary Sacrifice Calculator 2026/27 | UKSalarySacrificeCalculator.co.uk",
        meta_description="Estimate how salary sacrifice restores your personal allowance when income exceeds £100,000 in 2026/27.",
        canonical_url=SITE_URL + "/salary-sacrifice-100k-calculator",
        breadcrumbs=[
            {"name": "Home", "url": SITE_URL + "/"},
            {"name": "Calculators", "url": SITE_URL + "/calculators"},
            {"name": "£100k Tax Trap Calculator", "url": SITE_URL + "/salary-sacrifice-100k-calculator"},
        ],
    ))


@app.route("/employer-ni-saving-calculator")
def employer_ni_saving_calculator():
    return render_template("employer-ni-saving-calculator.html", **_ctx(
        title="Employer NI Saving Calculator 2026/27 | UKSalarySacrificeCalculator.co.uk",
        meta_description="Estimate employer National Insurance savings from salary sacrifice and optional pension passthrough.",
        canonical_url=SITE_URL + "/employer-ni-saving-calculator",
        breadcrumbs=[
            {"name": "Home", "url": SITE_URL + "/"},
            {"name": "Calculators", "url": SITE_URL + "/calculators"},
            {"name": "Employer NI Saving Calculator", "url": SITE_URL + "/employer-ni-saving-calculator"},
        ],
    ))


SACRIFICE_SALARY_AMOUNTS = [20000, 25000, 30000, 35000, 40000, 45000, 50000, 60000, 75000, 100000]


@app.route("/salary-sacrifice/<int:salary>")
def salary_sacrifice_page(salary: int):
    if salary not in SACRIFICE_SALARY_AMOUNTS:
        abort(404)
    # 5% pension sacrifice scenario
    sacrifice = round(salary * 0.05 / 500) * 500
    sacrifice = max(1000, min(sacrifice, 8000))
    calc = calculate_salary_sacrifice(
        gross_salary=salary,
        sacrifice_amount=sacrifice,
        sacrifice_type="pension",
        region="england_wales_ni",
        student_loan_plan="none",
    )
    total_saving = calc.income_tax_saving + calc.employee_ni_saving
    return render_template("salary_sacrifice_page.html", **_ctx(
        title=f"Salary Sacrifice on £{salary:,} Salary 2026/27 | Calculator",
        meta_description=f"How much does salary sacrifice save on a £{salary:,} salary in 2026/27? A £{sacrifice:,} pension sacrifice saves approximately £{total_saving:,.0f} in tax and NI.",
        canonical_url=SITE_URL + f"/salary-sacrifice/{salary}",
        salary=salary,
        sacrifice=sacrifice,
        calc=calc,
        all_salaries=SACRIFICE_SALARY_AMOUNTS,
        breadcrumbs=[
            {"name": "Home", "url": SITE_URL + "/"},
            {"name": f"Salary sacrifice on £{salary:,}", "url": SITE_URL + f"/salary-sacrifice/{salary}"},
        ],
    ))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
