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


@app.route("/ads.txt")
def ads_txt():
    pub_id = ADSENSE_CLIENT.replace("ca-pub-", "").strip()
    body = f"google.com, pub-{pub_id}, DIRECT, f08c47fec0942fa0\n" if pub_id else ""
    resp = make_response(body)
    resp.mimetype = "text/plain"
    return resp


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
        (f"{SITE_URL}/salary-sacrifice-pension", "0.6", "monthly"),
        (f"{SITE_URL}/guides", "0.6", "monthly"),
        (f"{SITE_URL}/calculators", "0.6", "monthly"),
        (f"{SITE_URL}/pension-salary-sacrifice-calculator", "0.7", "monthly"),
        (f"{SITE_URL}/bonus-sacrifice-calculator", "0.7", "monthly"),
        (f"{SITE_URL}/salary-sacrifice-100k-calculator", "0.7", "monthly"),
        (f"{SITE_URL}/employer-ni-saving-calculator", "0.7", "monthly"),
        (f"{SITE_URL}/blog", "0.6", "weekly"),
    ] + [(f"{SITE_URL}/blog/{p['slug']}", "0.6", "monthly") for p in BLOG_POSTS] \
      + [(f"{SITE_URL}/salary-sacrifice/{s}", "0.5", "monthly") for s in SACRIFICE_SALARY_AMOUNTS]
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


@app.route("/salary-sacrifice-pension")
def guide_pension_scheme():
    return render_template("salary-sacrifice-pension.html", **_ctx(
        title="Salary Sacrifice for Pensions — How It Works 2026/27 | UK Guide",
        meta_description="How pension salary sacrifice works in 2026/27: income tax and NI savings, employer NI passthrough, the annual allowance and opting in via your employer.",
        canonical_url=SITE_URL + "/salary-sacrifice-pension",
        breadcrumbs=[{"name": "Home", "url": SITE_URL + "/"}, {"name": "Salary Sacrifice for Pensions", "url": SITE_URL + "/salary-sacrifice-pension"}],
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


SACRIFICE_SALARY_AMOUNTS = [20000, 25000, 30000, 35000, 40000, 45000, 50000, 55000, 60000, 70000, 75000, 80000, 100000]


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


BLOG_POSTS = [
    {
        "slug": "salary-sacrifice-explained",
        "title": "Salary Sacrifice Explained — How It Works in the UK",
        "description": "A complete guide to salary sacrifice: how a formal contract change saves income tax and National Insurance, what benefits qualify, and the important considerations before you sacrifice.",
        "date": "26 May 2026",
        "date_iso": "2026-05-26",
        "reading_time": "7 min read",
        "sections": [
            {
                "heading": "What Salary Sacrifice Is",
                "paragraphs": [
                    "Salary sacrifice is a formal change to your employment contract. You agree with your employer to give up a portion of your gross cash salary in exchange for a non-cash benefit — typically a pension contribution, a company electric car, cycle-to-work equipment or a technology package. HMRC approves this arrangement, and the tax savings arise because income tax and National Insurance are both calculated on your reduced gross salary, not on the original figure.",
                    "The key word is formal. A salary sacrifice arrangement must genuinely amend your employment contract — it is not simply a request to have your pension contribution handled differently. HMRC scrutinises arrangements that appear to allow flexible switching in and out at will, since that would resemble a salary supplement rather than a genuine contract change. Most employers set specific windows for joining or altering the scheme.",
                ],
            },
            {
                "heading": "How the Mechanics Work",
                "paragraphs": [
                    "Under salary sacrifice, your contractual gross salary reduces by the sacrifice amount. Your employer then provides the benefit — usually by paying the pension contribution directly, or by leasing a car and making it available to you. Because your gross salary is lower, PAYE income tax is assessed on a smaller figure, and employee National Insurance contributions are assessed on a smaller figure too.",
                    "Your employer also benefits: employer NI (15% in 2026/27 on earnings above £5,000) is calculated on your reduced salary, saving the employer money on every pound sacrificed. This employer NI saving is real cash — it is not simply redistributed to you automatically, but many employers pass some or all of it back as additional pension contributions or enhanced scheme terms. The net effect is that a £1,000 salary sacrifice typically costs a basic-rate employee only around £720 in reduced take-home pay, because the income tax and NI savings absorb the rest.",
                ],
            },
            {
                "heading": "What Benefits Can Be Salary Sacrificed",
                "paragraphs": [
                    "HMRC permits salary sacrifice for a range of benefits. Pension contributions are the most common and most valuable — the employee and employer NI savings make them significantly more efficient than standard pension contributions. Company electric vehicles are highly tax-efficient thanks to the low BIK rate (4% for zero-emission cars in 2026/27). Cycle-to-work equipment is fully exempt from BIK tax, so the entire sacrifice is a tax saving with no offsetting charge. Technology packages (phones, laptops) can also qualify in some schemes.",
                    "What cannot be salary sacrificed: cash bonuses once they have been paid (though a pre-payment election to sacrifice a forthcoming bonus is possible under specific rules), contractual overtime pay, and any benefit that is itself cash or a cash voucher. Childcare vouchers closed to new entrants in October 2018 and are no longer available for new joiners, though existing members of grandfathered schemes may still be receiving them.",
                ],
            },
            {
                "heading": "Important Considerations Before You Sacrifice",
                "paragraphs": [
                    "The reduced gross salary created by sacrifice affects several other calculations that use salary as an input. Mortgage lenders may assess affordability on your contractual (post-sacrifice) salary — if you are planning to apply for a mortgage in the near term, discuss this with a mortgage broker before altering your sacrifice level. Some lenders accept a letter from your employer confirming the true gross pay, but others simply use the P60 figure.",
                    "Statutory Maternity Pay (SMP) and Statutory Paternity Pay are both calculated on average earnings. If your salary is reduced by sacrifice during the relevant reference period (typically the 8 weeks before the 25th week of pregnancy for SMP), your statutory entitlement may be lower. Some employers top up statutory payments to full salary, rendering this moot — but check your employer's policy before committing to a sacrifice that spans a period near a planned or possible maternity leave.",
                ],
            },
        ],
        "faqs": [
            {"q": "What is the difference between salary sacrifice and a normal pension contribution?", "a": "Salary sacrifice reduces your gross salary and saves both income tax and National Insurance on the sacrificed amount. A normal employee contribution under relief at source only saves income tax. The NI saving (8% for most employees) is the additional benefit of salary sacrifice."},
            {"q": "Can my employer refuse to let me use salary sacrifice?", "a": "Yes. Salary sacrifice must be offered by the employer — you cannot set it up unilaterally. If your employer does not offer a scheme, you can ask them to consider introducing one, noting that they also save 15% employer NI on the sacrificed amount."},
            {"q": "Does salary sacrifice reduce my take-home pay?", "a": "Your gross salary falls, but your take-home pay typically falls by less than the sacrifice amount because you save income tax and NI. For a basic-rate taxpayer, a £1,000 sacrifice reduces take-home pay by approximately £720."},
        ],
        "sources": [
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "HMRC: National Insurance rates and categories", "url": "https://www.gov.uk/national-insurance-rates-letters"},
        ],
    },
    {
        "slug": "salary-sacrifice-pension-guide",
        "title": "Salary Sacrifice for Pensions — Full Guide 2026/27",
        "description": "Why pension salary sacrifice saves more than standard contributions, the NI saving, employer passthrough, the annual allowance limit and how to opt in.",
        "date": "26 May 2026",
        "date_iso": "2026-05-26",
        "reading_time": "7 min read",
        "sections": [
            {
                "heading": "Why Pension Salary Sacrifice Saves More Than Standard Contributions",
                "paragraphs": [
                    "A standard employee pension contribution made under relief at source saves income tax on the contribution but not National Insurance. The provider claims 20% basic-rate relief from HMRC; higher-rate taxpayers then claim additional relief via Self Assessment. NI is not affected — you pay NI on your full gross salary whether or not you make pension contributions.",
                    "Salary sacrifice works differently: your gross salary is reduced, so employee NI is assessed on a lower figure. A £3,000 annual pension sacrifice for someone earning £35,000 saves 20% × £3,000 = £600 in income tax plus 8% × £3,000 = £240 in NI — a total saving of £840 per year. The same £3,000 contribution under relief at source saves only £600. Over a career of 30 years at that sacrifice level, the NI saving alone amounts to £7,200 in additional retirement savings at no extra cost to the employee.",
                ],
            },
            {
                "heading": "Employer NI Sharing",
                "paragraphs": [
                    "Your employer saves 15% employer NI on every pound sacrificed. On a £3,000 annual sacrifice, that is £450 per year that the employer no longer pays to HMRC. Many employers share this saving with employees by directing it into the pension as additional employer contribution. If your employer passes back 100%, your pension receives £3,450 from a £3,000 sacrifice. If they pass back 50%, your pension receives £3,225.",
                    "There is no legal requirement for employers to pass on the NI saving, so practice varies. Ask HR directly — specifically whether 'NI matching' or 'NI passthrough' applies to your scheme and what the percentage is. For a scheme where the employer passes back 100% of their NI saving, salary sacrifice into a pension is significantly more efficient than any other pension contribution method available to employed workers.",
                ],
            },
            {
                "heading": "The Limits",
                "paragraphs": [
                    "The pension annual allowance is £60,000 for 2026/27. All pension inputs count — your sacrifice, employer contributions (including NI passthrough), and any contributions to other pensions. For most employees making modest sacrifices, the £60,000 limit is never an issue. For higher earners making large sacrifices with substantial employer contributions, it can become relevant — particularly for those who are also members of defined benefit schemes where annual accrual counts towards the allowance.",
                    "The National Minimum Wage floor is the other constraint: your post-sacrifice cash salary must not fall below NMW for your age. For a full-time worker aged 21+ on NMW (£12.21 per hour in 2026/27), the full-time annual equivalent is approximately £23,600. Any sacrifice that takes cash pay below this level is not permitted. Most employees sacrificing typical pension amounts are not near this floor, but it limits how aggressively lower-paid workers can use the scheme.",
                ],
            },
            {
                "heading": "Opting In via Your Employer",
                "paragraphs": [
                    "Salary sacrifice is a contractual arrangement — you need your employer to operate the scheme and you need to sign a salary sacrifice agreement. The agreement specifies the amount to be sacrificed, the benefit to be provided (pension contribution), and typically the period. Some agreements are open-ended (the sacrifice continues until you cancel), others are fixed for a tax year.",
                    "Most employers process changes at specific points — often the start of the tax year, January, or during an annual benefits review window. Once signed, the change should appear on your next payslip as a reduced gross salary and an employer pension contribution of the equivalent amount. If you later want to change the sacrifice level, you normally need to wait until the next available window. Keep a copy of your salary sacrifice agreement and check that your P60 at the end of the year reflects the arrangement correctly.",
                ],
            },
        ],
        "faqs": [
            {"q": "How much more do I save with salary sacrifice vs a normal pension contribution?", "a": "On a £3,000 annual contribution, salary sacrifice saves approximately £240 more per year for a basic-rate taxpayer (the 8% NI saving). For higher-rate taxpayers (2% NI above £50,270), the difference is smaller. The gap widens further if the employer passes back their NI saving."},
            {"q": "Does my employer have to match their NI saving?", "a": "No — there is no legal obligation. But many employers do pass back at least part of their NI saving because it is a recruitment and retention tool that costs them nothing (they are sharing a saving, not creating an expense)."},
            {"q": "Can I sacrifice my entire salary into a pension?", "a": "No. Your post-sacrifice cash salary must not fall below National Minimum Wage. You also cannot contribute more than 100% of your earnings to a pension, and the annual allowance caps total inputs at £60,000."},
        ],
        "sources": [
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "HMRC: Pension annual allowance", "url": "https://www.gov.uk/pension-annual-allowance"},
        ],
    },
    {
        "slug": "electric-car-salary-sacrifice-guide",
        "title": "Electric Car Salary Sacrifice — Is It Worth It?",
        "description": "How EV salary sacrifice works, the numbers compared to buying on finance, the risks if you leave the company, and who benefits most from the scheme.",
        "date": "26 May 2026",
        "date_iso": "2026-05-26",
        "reading_time": "7 min read",
        "sections": [
            {
                "heading": "How EV Salary Sacrifice Works",
                "paragraphs": [
                    "Under an electric car salary sacrifice scheme, your employer takes out a lease on a vehicle and provides it to you as a company car. You sacrifice enough salary to cover the monthly lease cost (typically including insurance and maintenance). Your gross salary reduces, so you pay less income tax and employee NI. The car is provided as a benefit in kind — you owe BIK income tax on 4% of the car's P11D value for 2026/27 (the 'appropriate percentage' for zero-emission vehicles).",
                    "For example: a £40,000 P11D EV generates a BIK value of £40,000 × 4% = £1,600. A basic-rate taxpayer pays 20% × £1,600 = £320 in annual BIK income tax. A higher-rate taxpayer pays 40% × £1,600 = £640. Against this, the salary sacrifice itself saves income tax and NI — so the net cost depends on the size of the sacrifice versus the BIK charge. For most EVs in 2026/27 the NI and income tax savings substantially exceed the BIK charge, making the scheme financially attractive.",
                ],
            },
            {
                "heading": "The Numbers: Salary Sacrifice vs Buying on Finance",
                "paragraphs": [
                    "Consider a higher-rate taxpayer (income £55,000) using EV salary sacrifice for a £35,000 P11D car with a monthly lease cost of £550 (£6,600 per year). Annual sacrifice: £6,600. Income tax saving (40%): £2,640. Employee NI saving (2% — income is above UEL): £132. Total personal annual saving: £2,772. BIK tax owed: 40% × (£35,000 × 4%) = 40% × £1,400 = £560. Net annual cost: £6,600 − £2,772 + £560 = £4,388, or approximately £366 per month including insurance and maintenance.",
                    "An equivalent private lease of the same car (£550/month, excluding insurance and maintenance which would be additional) comes from post-tax income. At 40% tax and 2% NI, the employee needs to earn approximately £942 in gross income to have £550 of net pay to spend on the lease. The effective gross cost of the private lease is approximately £11,300 per year versus £4,388 net through salary sacrifice — a saving of approximately £6,912 per year for a higher-rate taxpayer. The saving is lower for basic-rate taxpayers but still very significant.",
                ],
            },
            {
                "heading": "The Risks",
                "paragraphs": [
                    "The main risk is leaving the company before the lease ends. You are party to a salary sacrifice agreement that runs for the lease term — typically 2–4 years. If you resign or are made redundant, your employer may hold you responsible for early termination costs, which can be substantial (often 50–80% of remaining lease payments). Read the early termination clause in your scheme agreement before signing — it is the single most important piece of small print.",
                    "Excess mileage charges apply if you exceed the agreed annual mileage at lease end. These can be significant on EVs that are driven heavily for business. Insurance excesses and damage charges follow the scheme's terms rather than personal insurance terms, which may differ from what you are used to. The BIK rate is rising each year — 4% in 2026/27, 5% in 2027/28, 7% in 2028/29 — so the net savings over a 3-year lease are lower in years 2 and 3 than in year 1.",
                ],
            },
            {
                "heading": "Who It Works Best For",
                "paragraphs": [
                    "Higher-rate taxpayers benefit significantly more than basic-rate taxpayers. The income tax saving is 40% versus 20%, and the BIK charge is at the same rate — so the net benefit is proportionally larger at higher income. The NI saving is smaller above £50,270 (2% rather than 8%), which slightly narrows the advantage for the highest earners, but the income tax differential still makes EV sacrifice highly attractive.",
                    "People who drive enough miles to justify an EV's range but not so many that excess mileage charges become a concern are the ideal candidates. Those in stable employment who do not anticipate changing jobs within the lease term avoid the early termination risk. And those for whom the 4% BIK rate represents good value relative to the car they would otherwise drive on personal funds — which for most people is a cheaper second-hand car — will get the most from the scheme.",
                ],
            },
        ],
        "faqs": [
            {"q": "What is the BIK rate for electric cars in 2026/27?", "a": "4% of the P11D value. This is the annual income tax charge: multiply P11D by 4% to get the BIK value, then multiply by your income tax rate. A £40,000 EV costs a higher-rate taxpayer £640 per year in BIK tax."},
            {"q": "What happens if I leave my job while on an EV scheme?", "a": "You may be liable for early termination costs under the salary sacrifice agreement. These can be substantial. Always read the early termination clause before signing — it is the key risk of EV salary sacrifice."},
            {"q": "Is EV salary sacrifice worth it for a basic-rate taxpayer?", "a": "Yes, usually — the income tax saving (20%) and NI saving (8%) together typically outweigh the BIK charge. But the saving is larger for higher-rate taxpayers because the income tax saving is 40%."},
        ],
        "sources": [
            {"label": "HMRC: Company car tax — benefit in kind rates", "url": "https://www.gov.uk/government/publications/rates-and-allowances-hmrc-company-car-tax"},
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
        ],
    },
    {
        "slug": "salary-sacrifice-student-loans",
        "title": "Salary Sacrifice and Student Loans — Does It Reduce Repayments?",
        "description": "Salary sacrifice reduces gross pay — which is the figure used for student loan repayments. But HMRC's confirmed position is more nuanced than it first appears. Here is what you need to know.",
        "date": "26 May 2026",
        "date_iso": "2026-05-26",
        "reading_time": "6 min read",
        "sections": [
            {
                "heading": "How Student Loan Repayments Are Calculated",
                "paragraphs": [
                    "Student loan repayments for Plans 1, 2, 4 and 5 are calculated as a percentage of income above the relevant threshold. For Plan 2 (the most common for graduates from 2012 onwards), the threshold is £27,295 for 2026/27. The repayment rate is 9% on income above this level. The income figure used is effectively gross employment income — specifically, the annual equivalent of the PAYE income reported to HMRC.",
                    "Salary sacrifice reduces the gross salary that is reported to HMRC under PAYE. A salary of £35,000 with a £3,000 annual pension sacrifice produces a PAYE income figure of £32,000. Student loan repayments are then 9% × (£32,000 − £27,295) = 9% × £4,705 = approximately £423 per year, instead of 9% × (£35,000 − £27,295) = 9% × £7,705 = approximately £693 per year. The sacrifice reduces repayments by approximately £270 per year.",
                ],
            },
            {
                "heading": "The Rare Exception",
                "paragraphs": [
                    "In the vast majority of cases, salary sacrifice genuinely reduces the PAYE income figure that is used for student loan repayments. The calculation operates on taxable pay, and salary sacrifice reduces taxable pay. There is no specific add-back or adjustment for pension sacrifice in the student loan calculation — HMRC applies the repayment to the PAYE income figure as submitted.",
                    "The scenario where this might not hold is where an employer incorrectly calculates PAYE on the pre-sacrifice salary or where a PAYE coding notice overrides the calculation in an unusual way. These are edge cases involving payroll errors rather than a policy exception. In normal operation, pension salary sacrifice does reduce the income figure used for student loan repayments.",
                ],
            },
            {
                "heading": "When This Advice Matters",
                "paragraphs": [
                    "The interaction becomes significant for people on Plan 2 with income near the £27,295 threshold. If your income (after sacrifice) falls below the threshold, your repayments stop entirely. A small sacrifice of £1,000 for someone earning £28,000 could eliminate their Plan 2 repayments altogether — a saving of 9% × (£28,000 − £27,295) = approximately £63 per year. This is modest, but for someone who expects their loan to be written off before repayment is complete (typically after 30 years on Plan 2), every repayment avoided is a genuine saving.",
                    "However, for someone who will repay their loan in full before the write-off date, reducing repayments by sacrificing salary actually increases total interest paid — because the loan balance reduces more slowly. Run the numbers for your specific loan balance, interest rate and expected earnings trajectory before deciding whether reducing repayments through salary sacrifice is beneficial.",
                ],
            },
            {
                "heading": "What Actually Reduces Student Loan Repayments",
                "paragraphs": [
                    "The most direct ways to reduce student loan repayments are: reducing your income (working fewer hours, taking unpaid leave), salary sacrifice into qualifying schemes (pension, EV, cycle to work — all reduce gross pay), or making voluntary capital repayments directly to the Student Loans Company. The latter option only makes financial sense if your interest rate on the loan exceeds what you could earn elsewhere — for many Plan 2 borrowers the interest rate makes early repayment unattractive.",
                    "There is no mechanism to voluntarily pause or reduce repayments without reducing income — the repayment is deducted automatically through PAYE at the applicable rate on income above threshold. The only reliable lever is income itself.",
                ],
            },
        ],
        "faqs": [
            {"q": "Does pension salary sacrifice reduce student loan repayments?", "a": "Yes, in practice. Salary sacrifice reduces the PAYE income figure, and student loan repayments are calculated on that figure. A lower PAYE income means lower repayments."},
            {"q": "Should I use salary sacrifice to reduce my student loan repayments?", "a": "It depends on whether you will repay in full or rely on the write-off. If you will repay in full, reducing repayments extends the loan and increases interest — potentially a worse outcome. If the loan will be written off, every repayment avoided is a saving."},
            {"q": "What student loan plan do most graduates have?", "a": "Most UK graduates who started university from 2012 are on Plan 2, with a repayment threshold of £27,295 for 2026/27 and a 30-year write-off period."},
        ],
        "sources": [
            {"label": "GOV.UK: Student loan repayments", "url": "https://www.gov.uk/repaying-your-student-loan"},
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
        ],
    },
    {
        "slug": "employer-ni-savings-salary-sacrifice",
        "title": "Employer NI Savings from Salary Sacrifice — Who Benefits?",
        "description": "How the employer NI saving from salary sacrifice works, why some employers share it with employees and others don't, the maths for a typical firm and how to negotiate a better deal.",
        "date": "26 May 2026",
        "date_iso": "2026-05-26",
        "reading_time": "7 min read",
        "sections": [
            {
                "heading": "How Employer NI Saving Works",
                "paragraphs": [
                    "Employer secondary National Insurance is charged at 15% on employee earnings above the secondary threshold (£5,000 per year for 2026/27). When an employee sacrifices salary, their gross pay is reduced, and employer NI is calculated on the lower figure. For every £1,000 of salary sacrifice, the employer saves 15% × £1,000 = £150. This is a genuine cash saving for the business — not a deferral or redistribution, but an actual reduction in payroll tax.",
                    "The saving arises from the moment the salary sacrifice arrangement takes effect and recurs for as long as the sacrifice continues. For an employee sacrificing £5,000 per year, the employer saves £750 per year indefinitely. This is why employers — particularly larger ones — are genuinely motivated to offer well-structured salary sacrifice schemes: the financial benefit to the business of running the scheme can be substantial, especially for large workforces.",
                ],
            },
            {
                "heading": "Do Employees See the Saving?",
                "paragraphs": [
                    "There is no legal obligation for employers to share their NI saving with employees. Many keep the full saving. However, a significant number — particularly larger organisations, financial services firms, professional services practices and technology companies — direct all or part of the saving into employees' pensions as additional employer contributions. This is known as NI matching or NI passthrough.",
                    "When an employer passes back 100% of their NI saving, the employee's pension receives the sacrifice amount plus the employer's NI saving. On a £5,000 annual sacrifice, the pension receives £5,750 — the employee's net pay reduces by only the post-tax cost of the £5,000 sacrifice (approximately £3,400 for a basic-rate employee), and the pension receives £5,750. The ratio of pension input to net pay reduction is extraordinary.",
                ],
            },
            {
                "heading": "The Maths for the Employer",
                "paragraphs": [
                    "For a 50-person company where each employee sacrifices an average of £5,000 per year into pension: employer NI saving = 15% × £5,000 × 50 = £37,500 per year. This is a recurring annual saving at no cost to the employees — in fact employees are better off as well. For larger firms the numbers scale proportionally: a 500-person company with the same average sacrifice saves £375,000 per year in employer NI.",
                    "These are material sums that justify the cost of establishing and administering a salary sacrifice scheme. Many employers choose to absorb the full employer NI saving as profit (or reinvest it in the business) rather than sharing it. But the best-designed schemes — particularly those competing for talent in professional services and technology — use the NI saving to fund enhanced pension contributions, which are a highly valued employee benefit at zero marginal cost to the employer.",
                ],
            },
            {
                "heading": "Salary Sacrifice as a Retention Tool",
                "paragraphs": [
                    "The employer NI saving makes salary sacrifice one of the few employee benefits that is genuinely cost-neutral (or better) for the employer while being valuable to employees. This is why companies increasingly use salary sacrifice as part of a broader benefits suite — electric cars, cycle to work, technology schemes and pension sacrifice all combined. Employees who are using multiple sacrifice schemes build substantial locked-in benefits that make them less inclined to leave; replacement hires would have to rebuild those benefits from scratch.",
                    "When evaluating a job offer, the quality of the employer's salary sacrifice scheme deserves explicit consideration. Two offers at the same gross salary may have very different net costs depending on whether one employer passes back NI savings, matches pension contributions generously, and offers a broader scheme including EVs. Ask detailed questions in the recruitment process: it is a legitimate and increasingly expected area of scrutiny.",
                ],
            },
        ],
        "faqs": [
            {"q": "What is the employer NI saving on a £5,000 salary sacrifice?", "a": "15% × £5,000 = £750 per year. This is a cash saving for the employer, not a transfer from elsewhere in the business."},
            {"q": "How do I find out if my employer passes on NI savings?", "a": "Ask HR or payroll directly: 'Does the company pass on its employer NI savings from salary sacrifice as additional pension contributions, and if so, at what percentage?' It is not always prominently advertised."},
            {"q": "If my employer keeps the NI saving, is salary sacrifice still worth it for me?", "a": "Yes — you still save employee NI (8% at main rate) and income tax on the sacrifice. The employer NI passthrough is an additional bonus if available, but the scheme is financially worthwhile for employees regardless of whether the employer shares their saving."},
        ],
        "sources": [
            {"label": "HMRC: Employer NI rates and secondary contributions", "url": "https://www.gov.uk/national-insurance-rates-letters"},
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "The Pensions Regulator: Employer pension duties", "url": "https://www.thepensionsregulator.gov.uk/en/employers"},
        ],
    },
    {
        "slug": "salary-sacrifice-scotland-2026",
        "title": "Salary Sacrifice in Scotland 2026/27: Income Tax Bands and NI Savings Explained",
        "description": "Scottish taxpayers have five income tax bands, not the two used in rUK. This changes how much you save on income tax through salary sacrifice — though the NI saving is identical across the UK.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "6 min read",
        "faqs": [
            {"q": "Do Scottish taxpayers save more NI through salary sacrifice?", "a": "No. National Insurance is reserved to Westminster, so the rates and thresholds are identical for Scottish and rUK employees. The NI saving from salary sacrifice is the same wherever you live."},
            {"q": "How do I select Scottish rates in the calculator?", "a": "Use the region dropdown in the calculator and select 'Scotland'. The calculator applies the five Scottish income tax bands automatically."},
            {"q": "What is the Scottish intermediate rate in 2026/27?", "a": "The Scottish intermediate rate for 2026/27 is 21%, applying to earnings between the basic rate upper limit and the intermediate threshold. This is 1 percentage point higher than the rUK basic rate of 20%, which means salary sacrifice into a pension saves fractionally more income tax for intermediate-rate Scottish taxpayers."},
        ],
        "sections": [
            {
                "heading": "Scotland's five income tax bands",
                "paragraphs": [
                    "In 2026/27 Scottish taxpayers face five distinct income tax bands: 19% starter rate (£12,571–£15,397), 20% basic rate (£15,398–£27,491), 21% intermediate rate (£27,492–£43,662), 42% higher rate (£43,663–£75,000), and 45% top rate above £75,000. This contrasts with rUK, which has just three bands: 20%, 40% and 45%. The key difference for salary sacrifice planning is that Scotland's intermediate rate of 21% applies to a significant band of mid-range earnings where rUK basic-rate taxpayers would pay only 20%.",
                    "Because salary sacrifice reduces your gross pay before income tax is assessed, it saves you tax at your marginal rate. For a Scottish taxpayer earning £35,000 — firmly in the 21% intermediate band — sacrificing £2,000 into a pension saves £420 in income tax (21% × £2,000), compared to £400 for an rUK basic-rate taxpayer (20% × £2,000). The difference is modest but real, and stacks on top of the NI saving.",
                ],
            },
            {
                "heading": "The NI saving is UK-wide",
                "paragraphs": [
                    "National Insurance contributions are a reserved matter, set by Westminster and charged at the same rates across Scotland, England, Wales and Northern Ireland. For 2026/27 the employee NI rate is 8% on earnings between £12,570 and £50,270, and 2% above that. When you sacrifice salary, those earnings disappear from the NI calculation altogether — so a Scottish employee on £35,000 sacrificing £2,000 saves the same £160 in employee NI as someone in Manchester or Cardiff.",
                    "Employer NI is also unchanged across the UK. Employers pay 15% secondary NI on employee earnings above the secondary threshold of £5,000. A £2,000 salary sacrifice saves the employer £300 in NI. Many employers pass this saving on to employees as additional pension contributions — particularly valuable in Scotland where combined income tax and NI savings are slightly higher for intermediate-rate earners.",
                ],
            },
            {
                "heading": "Worked example: Scottish taxpayer at £35,000",
                "paragraphs": [
                    "Consider a Scottish employee earning £35,000 who sacrifices £2,000 per year into a pension. Their income tax saving is 21% × £2,000 = £420 (using the intermediate rate). Their employee NI saving is 8% × £2,000 = £160. Total personal saving: £580 per year, or £48.33 per month. The gross cost to their net pay is therefore only £2,000 − £580 = £1,420, or roughly 71p in the pound.",
                    "Compare this to an rUK basic-rate taxpayer on the same salary: income tax saving is 20% × £2,000 = £400, NI saving £160, total £560. The Scottish taxpayer saves £20 more per year simply because their marginal income tax rate is 1 percentage point higher. At higher Scottish bands the difference is more pronounced — a Scottish higher-rate taxpayer at 42% saves significantly more in income tax than an rUK higher-rate taxpayer at 40%.",
                ],
            },
            {
                "heading": "Higher and top rate Scottish taxpayers",
                "paragraphs": [
                    "Scotland's higher rate of 42% applies from £43,663, which is lower than the rUK higher rate threshold of £50,270. This means Scottish higher earners enter the 42% band earlier and benefit from the full 42% income tax saving on pension sacrifice in that range. An employee earning £50,000 in Scotland has earnings between £43,663 and £50,000 taxed at 42% — if they sacrifice £3,000 into a pension that crosses or falls within this band, part of the saving is at 42% rather than the rUK 40%.",
                    "Scotland's top rate of 45% applies above £75,000, compared to the rUK additional rate which also starts at £125,140 (after personal allowance withdrawal). High-earning Scots therefore benefit from very substantial salary sacrifice income tax savings. A Scottish taxpayer at £80,000 sacrificing £5,000 saves 45% × £5,000 = £2,250 in income tax alone. Adding the NI saving makes the combined benefit compelling.",
                ],
            },
            {
                "heading": "Using the calculator",
                "paragraphs": [
                    "Our salary sacrifice calculator includes a Scotland region option that applies the five Scottish income tax bands correctly. Enter your gross salary, your intended sacrifice amount, and the type of scheme (pension, cycle to work, EV car). The calculator will show you the income tax saving at Scottish rates, the NI saving (identical to rUK), the employer NI saving, and the net monthly cost of the sacrifice.",
                ],
            },
        ],
        "sources": [
            {"label": "Scottish Government: Income Tax Rates 2026/27", "url": "https://www.gov.scot/policies/taxes/income-tax/"},
            {"label": "HMRC: National Insurance rates and categories", "url": "https://www.gov.uk/national-insurance-rates-letters"},
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
        ],
    },
    {
        "slug": "salary-sacrifice-vs-ras-2026",
        "title": "Salary Sacrifice vs Relief at Source vs Net Pay Arrangement 2026/27",
        "description": "Three ways to get pension tax relief — and they are not equivalent. Salary sacrifice removes gross pay entirely; NPA gives full marginal-rate relief automatically; RaS requires a Self Assessment claim for higher-rate top-up. Here is how to choose.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "7 min read",
        "faqs": [
            {"q": "Which method saves the most for a basic-rate taxpayer?", "a": "For a basic-rate taxpayer, salary sacrifice saves the most because you also avoid 8% employee NI on the sacrificed amount in addition to the income tax saving. Under RaS or NPA you get 20% tax relief but no NI saving. Salary sacrifice is strictly better for employed people where the scheme is available."},
            {"q": "Does salary sacrifice affect my state pension?", "a": "Only if your post-sacrifice salary falls below the Lower Earnings Limit (£6,396 for 2026/27). Most people are well above this. If you are close to the LEL, check with your employer before agreeing a large sacrifice."},
            {"q": "What is the difference between NPA and RaS?", "a": "Under a net pay arrangement (NPA), contributions are deducted from gross salary before tax is calculated, so you receive relief at your full marginal rate without any claim. Under relief at source (RaS), you pay the net amount (80%), the provider claims 20% from HMRC, and higher-rate taxpayers must claim the additional 20% or 25% via Self Assessment."},
        ],
        "sections": [
            {
                "heading": "The three routes to pension tax relief",
                "paragraphs": [
                    "When money goes into a UK pension, the government provides tax relief to recognise that contributions come from income that has already been (or will be) taxed. There are three different mechanisms used in practice: relief at source (RaS), net pay arrangement (NPA), and salary sacrifice. Each operates differently, delivers different amounts of relief to different types of taxpayer, and involves different admin.",
                    "Relief at source is used by most personal pensions and SIPPs. You contribute the net amount — 80p to receive £1 in the pension — and your provider automatically claims the 20% basic-rate top-up from HMRC. If you pay 40% or 45% income tax, you must claim the extra 20% or 25% yourself via Self Assessment or by contacting HMRC. Net pay arrangement is used by many workplace schemes: contributions are deducted from gross pay before income tax is applied, so you never pay tax on the money in the first place. Salary sacrifice is different again — it is a contractual arrangement, not technically pension tax relief, where you give up a portion of your salary entirely and your employer makes the pension contribution instead.",
                ],
            },
            {
                "heading": "Salary sacrifice: the NI advantage",
                "paragraphs": [
                    "The key advantage of salary sacrifice over both RaS and NPA is that the sacrificed amount also avoids National Insurance. Under RaS and NPA, your gross salary is unchanged — you still pay NI on the full amount. Under salary sacrifice, your contractual salary is reduced, so you pay NI on a lower figure. At the main employee NI rate of 8%, a £1,000 sacrifice saves £80 in NI on top of the income tax saving.",
                    "Employers benefit too: employer NI of 15% applies to the reduced salary only, saving the employer £150 per £1,000 sacrificed. Many employers pass some or all of this saving back as an enhanced pension contribution. If your employer does this — known as NI matching or passthrough — your effective pension contribution rate is higher than the headline figure, at no extra cost to you.",
                ],
            },
            {
                "heading": "When NPA is better than RaS",
                "paragraphs": [
                    "For higher and additional-rate taxpayers who are not in a salary sacrifice scheme, a net pay arrangement is generally preferable to relief at source because relief is applied automatically at the correct marginal rate. Under RaS, a 40% taxpayer who forgets to claim the extra 20% on their Self Assessment return effectively receives only basic-rate relief — a costly mistake. Under NPA, the full 40% (or 45%) relief is built in.",
                    "However, NPA has historically disadvantaged non-taxpayers and those earning below the personal allowance. For 2024/25 onwards the government introduced a top-up payment for low earners in NPA schemes to address this disparity, but the administration is complex. Low earners in RaS schemes automatically receive 20% top-up even if they pay no income tax.",
                ],
            },
            {
                "heading": "Practical considerations: can you actually use salary sacrifice?",
                "paragraphs": [
                    "Salary sacrifice requires your employer to offer it as an option and to amend your contract of employment. You cannot unilaterally decide to sacrifice salary — it must be a formal arrangement. Not all employers offer it, particularly smaller businesses. Where it is offered, the scheme rules govern the minimum and maximum sacrifice amounts and which benefits qualify.",
                    "The sacrifice must not reduce your cash salary below the National Minimum Wage for your age group — a constraint that limits the available sacrifice amount for low-paid workers. Salary sacrifice can also reduce mortgage affordability assessments since lenders may look at contractual salary rather than gross-plus-benefits. These are edge cases for most employees, but worth checking if they apply to you.",
                ],
            },
            {
                "heading": "Summary comparison",
                "paragraphs": [
                    "For employed basic-rate taxpayers in a salary sacrifice scheme: always prefer sacrifice over RaS or NPA — it saves income tax plus NI. For employed higher-rate taxpayers in a sacrifice scheme: same applies, and the income tax saving is 40% or 42% (Scotland) versus just the 20% automatic RaS top-up. For self-employed: salary sacrifice is not available; use a SIPP under RaS and claim higher-rate relief via Self Assessment.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Salary sacrifice arrangements", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "HMRC: Tax on your private pension contributions", "url": "https://www.gov.uk/tax-on-your-private-pension/pension-tax-relief"},
            {"label": "HMRC: Registered pension schemes — relief at source", "url": "https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm044100"},
        ],
    },
    {
        "slug": "electric-car-salary-sacrifice-2026",
        "title": "Electric Car Salary Sacrifice 2026/27: BiK Rates, Tax and NI Savings Explained",
        "description": "With the benefit-in-kind rate on zero-emission cars at just 3% for 2025/26 (rising to 4% in 2026/27), electric vehicle salary sacrifice remains one of the most tax-efficient ways to get a new EV. Here is how the numbers work.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "7 min read",
        "faqs": [
            {"q": "What is the BiK rate for electric cars in 2026/27?", "a": "The benefit-in-kind rate for fully zero-emission (electric) cars is 4% of the car's P11D value in 2026/27, rising to 5% in 2027/28 and 7% in 2028/29. This is far below the rates for petrol and diesel cars, which range from 25% to 37% depending on CO2 emissions."},
            {"q": "Is an electric car through salary sacrifice always cheaper than buying outright?", "a": "It is usually significantly cheaper in total cost of ownership terms, especially for higher-rate taxpayers, because the BiK tax is much lower than the income tax and NI you would have paid on the equivalent salary. The employer also saves NI. But you need to weigh the monthly sacrifice cost, the BiK charge, insurance and any excess mileage charges against alternative options."},
            {"q": "What happens to the car at the end of the scheme?", "a": "At the end of the scheme term (typically 2–4 years), you usually return the car to the employer or leasing company. Some schemes offer an option to purchase at market value. The salary sacrifice arrangement ends and your gross pay returns to normal."},
        ],
        "sections": [
            {
                "heading": "How electric car salary sacrifice works",
                "paragraphs": [
                    "Under an EV salary sacrifice scheme, your employer leases an electric car and provides it to you as a benefit. You sacrifice a portion of your gross salary — typically the monthly lease cost plus insurance and maintenance — and in return you get use of the car. Because your gross salary is reduced, you pay less income tax and National Insurance. Your employer also saves 15% employer NI on the sacrificed amount, which some pass on to you in the form of a reduced sacrifice contribution.",
                    "The car is provided to you as a company car, which means it is subject to benefit-in-kind (BiK) tax. You pay income tax on the BiK value, which is calculated as P11D value × BiK percentage. For a zero-emission car in 2026/27, the BiK rate is 4%. So a £40,000 EV has a BiK value of £40,000 × 4% = £1,600 per year. A basic-rate taxpayer pays 20% × £1,600 = £320 in income tax on the benefit. A higher-rate taxpayer pays 40% × £1,600 = £640.",
                ],
            },
            {
                "heading": "Worked example at £40,000 salary",
                "paragraphs": [
                    "Take an employee earning £40,000 who uses salary sacrifice to get a £35,000 P11D-value EV, with a monthly salary sacrifice of £600 (£7,200 per year). Their gross salary drops from £40,000 to £32,800. Income tax saving: approximately £7,200 × 20% = £1,440 (all in the basic-rate band). Employee NI saving: £7,200 × 8% = £576. Total annual saving before BiK tax: £2,016.",
                    "The BiK charge is £35,000 × 4% × 20% (basic-rate tax) = £280 per year. Net annual saving after BiK tax: £2,016 − £280 = £1,736. This means the employee is effectively getting a £35,000 electric car at a net cost of £7,200 − £1,736 = £5,464 per year — roughly £455 per month — instead of paying the full lease cost from after-tax income. For a higher-rate taxpayer, the income tax saving is 40% rather than 20%, making the deal even more attractive.",
                ],
            },
            {
                "heading": "BiK rate trajectory: plan ahead",
                "paragraphs": [
                    "The EV BiK rate has been deliberately kept low to incentivise zero-emission vehicle adoption, but it is rising each year. The confirmed rates are: 2025/26 3%, 2026/27 4%, 2027/28 5%, 2028/29 7%, 2029/30 9%. If you are taking a 3-year lease starting in 2026/27, your BiK rate will change over the lease term. Factor in the 2027/28 (5%) and 2028/29 (7%) rates when calculating the total cost over the full scheme period.",
                    "Even at 9% in 2029/30, EV BiK is substantially lower than equivalent petrol or diesel rates (25%+). The salary sacrifice NI saving remains throughout, regardless of the BiK rate. So EV salary sacrifice will continue to offer meaningful savings even as the BiK rate rises.",
                ],
            },
            {
                "heading": "Employer NI saving and passthrough",
                "paragraphs": [
                    "On a £7,200 annual sacrifice, your employer saves 15% × £7,200 = £1,080 in secondary NI. Some employers pass this directly back to you as a reduction in the required sacrifice amount. If your employer passes back 50% of their NI saving, your net sacrifice drops by £540 per year — a meaningful additional benefit. Ask your HR or benefits team whether NI matching is available on EV schemes; it varies significantly between employers.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Company car tax rates 2026/27 (BiK rates)", "url": "https://www.gov.uk/government/publications/rates-and-allowances-hmrc-company-car-tax"},
            {"label": "HMRC: Salary sacrifice arrangements", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "OZEV: Workplace charging and EV schemes guidance", "url": "https://www.gov.uk/guidance/plug-in-car-van-and-motorcycle-grant"},
        ],
    },
    {
        "slug": "cycle-to-work-scheme-explained",
        "title": "Cycle to Work Scheme Explained: How Salary Sacrifice Reduces the Cost",
        "description": "The cycle to work scheme lets you get a bike and safety equipment through salary sacrifice, spreading the cost from pre-tax income. Your actual saving depends on your income tax and NI rate — here is how to work it out.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "5 min read",
        "faqs": [
            {"q": "Is there a cap on the cycle to work scheme?", "a": "There is no statutory cap, but individual scheme providers set their own limits. The original government guidance suggested £1,000, but many providers — including Cyclescheme, Gogeta and Green Commute Initiative — now facilitate orders well above that amount, particularly for e-bikes which can cost £3,000–£5,000."},
            {"q": "Can I keep the bike at the end?", "a": "Yes, in most cases. The scheme is structured as a hire agreement — you hire the bike from your employer. At the end of the hire period (usually 12 months) you are offered a fair market value purchase. HMRC has published fair market value tables. In practice the final purchase cost is small, and the overall deal is still very cost-effective."},
            {"q": "Does cycle to work affect my mortgage application?", "a": "As with all salary sacrifice, your contractual salary is reduced by the sacrifice amount during the scheme period. Some mortgage lenders base affordability on your contractual salary. If you are about to apply for a mortgage, it may be worth deferring the cycle to work agreement until after the application is completed."},
        ],
        "sections": [
            {
                "heading": "How the scheme works",
                "paragraphs": [
                    "Under the cycle to work scheme, your employer purchases a bike (and qualifying safety equipment) and lends it to you under a hire agreement. You repay the cost via a salary sacrifice from your gross pay, spread over the hire period — typically 12 or 18 months. Because the sacrifice comes from gross pay, you never pay income tax or National Insurance on that portion of your earnings. At the end of the hire period, the employer can sell the bike to you at fair market value.",
                    "The scheme applies to standard bikes, e-bikes and a wide range of safety accessories including helmets, lights, locks and high-visibility clothing. The equipment must be used at least partly for commuting. The benefit-in-kind rules are exempt for cycle to work equipment, meaning you do not pay any BiK tax — unlike company cars.",
                ],
            },
            {
                "heading": "Calculating your actual saving",
                "paragraphs": [
                    "Your saving depends on your marginal income tax rate and your NI rate. For a basic-rate taxpayer (20% income tax, 8% NI), the combined saving is 28% — so a £1,000 bike costs £720 net. For a higher-rate taxpayer (40% income tax, 2% NI above the upper earnings limit), the saving is 42% — the same £1,000 bike costs £580 net. For a Scottish intermediate-rate taxpayer (21% income tax, 8% NI), the combined saving is 29%, giving a net cost of £710.",
                    "These figures assume the full sacrifice amount sits within the relevant tax and NI bands. If the sacrifice straddles a threshold — for example if it pushes your income across the NI upper earnings limit — the saving on the excess is calculated at different rates. The calculator can account for this if you enter the correct starting salary and scheme amount.",
                ],
            },
            {
                "heading": "Employer benefits",
                "paragraphs": [
                    "Your employer also saves 15% employer NI on the sacrificed amount. On a £1,000 scheme the employer saves £150. Many employers pass this saving on to employees, effectively reducing the gross sacrifice cost. Some larger employers have dedicated cycle to work administrators and absorb all admin costs. Smaller employers may use a third-party scheme provider who charges an administration fee — typically 5–10% of the scheme value, which may reduce (but not eliminate) the net saving.",
                ],
            },
            {
                "heading": "Limits and eligibility",
                "paragraphs": [
                    "The scheme is open to all employed people whose employer participates. You must be taxed under PAYE and your post-sacrifice salary must not fall below the National Minimum Wage. As with all salary sacrifice, self-employed people are not eligible because they have no employer to operate the arrangement. Higher-value schemes (above £1,000) may need to be structured as consumer hire agreements rather than standard hire arrangements, which your employer's scheme provider should handle automatically.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Cycle to work scheme — technical guidance", "url": "https://www.gov.uk/government/publications/cycle-to-work-scheme-implementation-guidance"},
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
        ],
    },
    {
        "slug": "salary-sacrifice-reduce-childcare-costs",
        "title": "How Salary Sacrifice Can Reduce Childcare Costs: Adjusted Net Income and 30 Hours Free",
        "description": "Pension salary sacrifice reduces your adjusted net income (ANI). This can restore eligibility for 30 hours free childcare, avoid the high income child benefit charge, and lower your effective marginal rate. Here is how.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "6 min read",
        "faqs": [
            {"q": "What is the income limit for 30 hours free childcare?", "a": "In 2026/27 the 30 hours free childcare offer (for 3–4 year olds) requires both parents (or a single parent) to each earn at least the equivalent of 16 hours at NMW and less than £100,000 adjusted net income per year. If your ANI exceeds £100,000 due to income, salary sacrifice into a pension can bring it below that threshold and restore full eligibility."},
            {"q": "Is Tax-Free Childcare the same as salary sacrifice for childcare?", "a": "No. Tax-Free Childcare is a government scheme where for every 80p you pay into an online childcare account, the government adds 20p — giving up to £500 per child per quarter (£2,000 per year). It is separate from salary sacrifice. Salary sacrifice for childcare referred historically to childcare vouchers, which closed to new entrants in October 2018. The indirect benefit of salary sacrifice now is through ANI reduction, not direct childcare vouchers."},
            {"q": "Does salary sacrifice affect child benefit eligibility?", "a": "Yes. The High Income Child Benefit Charge (HICBC) applies when ANI exceeds £60,000. For every £200 of ANI above £60,000, 1% of child benefit is clawed back. At £80,000 ANI the charge equals the full benefit. Pension salary sacrifice reduces ANI, potentially reducing or eliminating the HICBC."},
        ],
        "sections": [
            {
                "heading": "What is adjusted net income and why does it matter?",
                "paragraphs": [
                    "Adjusted net income (ANI) is your total income after deducting gross pension contributions (not just relief received). It is the figure HMRC uses for several threshold tests. ANI above £100,000 triggers personal allowance tapering at £1 for every £2 of excess — creating an effective 60% marginal tax rate in the £100,000–£125,140 band. ANI above £60,000 triggers the High Income Child Benefit Charge. ANI above £100,000 also removes eligibility for the 30 hours free childcare offer.",
                    "Salary sacrifice reduces your gross pay, which directly reduces ANI. Unlike relief at source or net pay contributions which are added back under the gross basis, salary sacrifice reduces the starting income figure — so it is the most efficient method for bringing ANI below these thresholds.",
                ],
            },
            {
                "heading": "The 30 hours free childcare threshold",
                "paragraphs": [
                    "The 30 hours free childcare offer is available to families where each working parent (or single parent) earns less than £100,000 ANI and at least the equivalent of 16 hours per week at the National Living Wage. The £100,000 limit is a hard cliff — exceed it by £1 and you lose 15 hours of free provision per week. For a family using 30 hours, losing the additional 15 hours can cost thousands of pounds per year in childcare fees.",
                    "If your income is between £100,000 and approximately £110,000 and you have children aged 3–4, pension salary sacrifice is an extremely high-value strategy. Each pound sacrificed reduces ANI by £1. If £5,000 of salary sacrifice brings your ANI from £103,000 to £98,000, you restore 30-hour eligibility. The total value — childcare saving plus income tax saving at 60% effective rate plus NI saving — makes this one of the most compelling uses of salary sacrifice available.",
                ],
            },
            {
                "heading": "The High Income Child Benefit Charge",
                "paragraphs": [
                    "Child benefit for 2026/27 is £25.60 per week for the eldest child (£1,331 per year) and £16.95 per week for each additional child (£882 per year). The HICBC claws back 1% of total benefit for every £200 of ANI above £60,000. At £80,000 ANI the full benefit is repaid. If your ANI is between £60,000 and £80,000 and you receive child benefit, salary sacrifice can reduce the clawback meaningfully.",
                    "For example, ANI of £65,000 with one child: clawback = (£65,000 − £60,000) / £200 × 1% × £1,331 = 25% × £1,331 = £333. If salary sacrifice reduces ANI to £61,000: clawback = 5% × £1,331 = £67. Net saving from the clawback reduction alone: £266 per year, on top of the normal income tax and NI saving from the sacrifice.",
                ],
            },
            {
                "heading": "Worked example: ANI £103,000, two young children",
                "paragraphs": [
                    "A parent with two children aged 2 and 4, ANI of £103,000. They sacrifice £5,000 into a pension, reducing ANI to £98,000. Benefits: (1) Personal allowance restored: the £100k taper reduces the personal allowance by £1 for every £2 above £100k. At £103k the PA is reduced by £1,500, meaning 45% more tax on £1,500 = £675 saving. At £98k the PA is restored fully. (2) 30-hour childcare eligibility restored: saving potentially £5,000–£8,000+ per year in childcare fees. (3) Normal income tax saving on sacrifice at 40%: £2,000. (4) Employee NI saving: £5,000 × 2% (above UEL) = £100. Total saving substantially exceeds the £5,000 sacrificed.",
                ],
            },
        ],
        "sources": [
            {"label": "GOV.UK: 30 hours free childcare eligibility", "url": "https://www.gov.uk/30-hours-free-childcare"},
            {"label": "HMRC: High Income Child Benefit Charge", "url": "https://www.gov.uk/child-benefit-tax-charge"},
            {"label": "HMRC: Salary sacrifice for employees", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
        ],
    },
    {
        "slug": "salary-sacrifice-employer-ni-saving-guide",
        "title": "Employer NI Saving from Salary Sacrifice: How Much, How to Claim, What to Ask HR",
        "description": "Employers save 15% secondary National Insurance on every pound of salary sacrifice. Many pass this saving on to employees. Here is what you need to know about employer NI passthrough and how to negotiate it.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "6 min read",
        "faqs": [
            {"q": "Are employers required to pass on their NI saving?", "a": "No. There is no legal requirement for employers to pass on the employer NI saving from salary sacrifice. However, many do — either in full or partially — because it helps recruitment and retention, and the cost to the employer is genuinely zero (they are sharing a saving, not incurring an expense)."},
            {"q": "How do I find out if my employer passes on NI savings?", "a": "Ask your HR or payroll team directly. Specifically ask: 'Does the company pass on employer NI savings from salary sacrifice as additional pension contributions?' If the answer is yes, ask for the percentage passed through. Some schemes pass 100%, some 50%, and some none."},
            {"q": "What is the employer NI rate in 2026/27?", "a": "From April 2025, the employer secondary NI rate increased to 15% (up from 13.8%). The secondary threshold — the wage level above which employer NI applies — is £5,000 per year. So employers pay 15% NI on all salary above £5,000 per employee."},
        ],
        "sections": [
            {
                "heading": "How the employer NI saving arises",
                "paragraphs": [
                    "When an employee sacrifices salary, their gross pay is reduced. Employer National Insurance is calculated on gross pay above the secondary threshold (£5,000 in 2026/27) at a rate of 15%. By reducing gross pay, salary sacrifice directly reduces the employer's NI liability. For a single employee sacrificing £5,000 per year, the employer saves 15% × £5,000 = £750. For a team of 100 employees each sacrificing £5,000, the employer saves £75,000 per year.",
                    "This is a genuine cost saving for the employer — not a transfer from one pocket to another, but an actual reduction in payroll tax. HMRC permits employers to pass this saving on to employees in any form, including as additional employer pension contributions, enhanced salary sacrifice limits, or simply as a higher take-home benefit package.",
                ],
            },
            {
                "heading": "Full passthrough: the most employee-friendly arrangement",
                "paragraphs": [
                    "Under full passthrough, the employer directs 100% of their NI saving into the employee's pension alongside the employee's own sacrifice. On a £5,000 sacrifice, the employer adds £750 to the pension. This means the employee's pension receives £5,750 (£5,000 sacrifice + £750 employer NI passthrough), while their take-home pay reduces only by the post-tax cost of the £5,000 sacrifice (roughly £3,400 for a basic-rate taxpayer). The pension contribution efficiency is exceptional — each pound of net pay reduction delivers roughly £1.69 into the pension.",
                    "Full passthrough is most commonly offered by larger employers who have set up salary sacrifice schemes specifically with NI sharing in mind. Public sector employers, large financial services firms and technology companies often offer it. Where offered, it effectively supercharges the pension sacrifice return and should be strongly preferred over personal pension contributions made outside the scheme.",
                ],
            },
            {
                "heading": "Partial passthrough and common structures",
                "paragraphs": [
                    "Many employers offer partial passthrough — typically 50% of the NI saving, meaning they keep 50% for themselves and direct 50% to the employee's pension. On a £5,000 sacrifice this adds £375 to the pension. This is still a meaningful benefit. Some employers offer a tiered structure: 100% passthrough up to a contribution threshold, then a lower rate above it.",
                    "Where no passthrough is offered, the full employer NI saving accrues to the business. In this situation, employees still benefit from the employee NI saving (8% at main rate) and the income tax saving — the sacrifice is still financially worthwhile. But if you have leverage in salary negotiations, the absence of NI matching is a legitimate point to raise with an employer.",
                ],
            },
            {
                "heading": "What to ask your employer",
                "paragraphs": [
                    "Before entering into a salary sacrifice arrangement, ask HR the following questions. First: does the employer pass on any NI savings, and if so what percentage and in what form? Second: is the sacrifice amount flexible — can it be changed mid-year or only at specific windows? Third: does sacrificing salary affect any other employment benefits such as death-in-service cover, income protection or maternity pay, which are often calculated on contractual salary?",
                    "If your employer does not currently operate a salary sacrifice scheme, you can propose one. The employer will need to amend employment contracts and set up payroll arrangements, but the financial benefit to the employer (NI savings on all participating employees) often makes it worth pursuing. Provide our employer NI saving calculator output as a concrete illustration of the potential saving.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Employer NI rates and categories", "url": "https://www.gov.uk/national-insurance-rates-letters"},
            {"label": "HMRC: Salary sacrifice arrangements", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "The Pensions Regulator: Employer duties and salary sacrifice", "url": "https://www.thepensionsregulator.gov.uk/en/employers"},
        ],
    },
    {
        "slug": "salary-sacrifice-explained",
        "title": "Salary Sacrifice Explained: What It Is, How It Works, and Whether It Is Worth It",
        "description": "Salary sacrifice lets you give up part of your gross pay in exchange for a non-cash benefit — saving income tax and National Insurance in the process. This guide explains the mechanics, the maths, and when it makes sense.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "7 min read",
        "faqs": [
            {"q": "Does salary sacrifice reduce my take-home pay?", "a": "Your cash take-home goes down by less than the amount you sacrifice, because you save income tax and NI on the sacrificed amount. For a basic-rate taxpayer sacrificing £100, take-home drops by roughly £72 (after saving £20 income tax and £8 NI). You give up £100 of gross but only feel £72 less in your pocket."},
            {"q": "Can my employer refuse salary sacrifice?", "a": "Yes. Salary sacrifice requires a formal contract change and your employer must agree to operate the arrangement. Not all employers offer it. Where it is offered, the scheme rules set out which benefits qualify and what the minimum and maximum sacrifice amounts are."},
            {"q": "Is salary sacrifice the same as a pay cut?", "a": "Structurally yes — your contractual salary is reduced. But the trade-off is a non-cash benefit of equivalent or greater value, plus the tax and NI saving that comes from having a lower gross salary. Whether it is worth it depends on the benefit on offer and your personal tax position."},
        ],
        "sections": [
            {
                "heading": "What salary sacrifice actually is",
                "paragraphs": [
                    "Salary sacrifice — also called salary exchange — is a formal arrangement between you and your employer. You agree to give up a portion of your contractual gross salary, and your employer provides a non-cash benefit in its place. Common examples are pension contributions, electric vehicle leases, cycle to work equipment, and childcare vouchers (though vouchers closed to new entrants in 2018).",
                    "The arrangement must be recorded in writing as a change to your employment contract. It is not something you can apply unilaterally — your employer has to set up and agree to the scheme. Because your gross salary is reduced, you pay income tax and National Insurance on a smaller number. That is the core financial benefit.",
                ],
            },
            {
                "heading": "The tax and NI saving in plain numbers",
                "paragraphs": [
                    "Take a basic-rate taxpayer earning £35,000 who sacrifices £1,200 per year (£100 per month) into a pension. Their gross pay drops from £35,000 to £33,800. Income tax saving: £1,200 × 20% = £240. Employee NI saving: £1,200 × 8% = £96. Total annual personal saving: £336. That means their net monthly pay drops by only (£1,200 − £336) ÷ 12 = £72 per month, even though £100 per month is going into their pension.",
                    "For a higher-rate taxpayer the numbers are better still. At 40% income tax and 2% NI (above the upper earnings limit), the saving on £1,200 is £480 plus £24 = £504. Net monthly cost is (£1,200 − £504) ÷ 12 = £58. The employer also saves 15% secondary NI — in this case £180 — which some employers pass back as an additional pension contribution.",
                ],
            },
            {
                "heading": "What qualifies for salary sacrifice",
                "paragraphs": [
                    "HMRC permits salary sacrifice for employer pension contributions, employer-provided childcare (now closed to new entrants), cycle to work schemes, ultra-low emission vehicles (particularly EVs), and workplace nurseries. Annual leave purchase schemes are also sometimes structured as salary sacrifice. HMRC does not permit salary sacrifice for cash — the benefit must be a genuine non-cash item.",
                    "The most widely used form is pension salary sacrifice because it is the most straightforward to administer and the tax saving is the largest for most employees. EV schemes are the fastest-growing category due to the very low 4% benefit-in-kind rate on zero-emission cars in 2026/27.",
                ],
            },
            {
                "heading": "When salary sacrifice might not be right for you",
                "paragraphs": [
                    "Salary sacrifice reduces your contractual pay. This matters in three situations. First, mortgage applications: some lenders base affordability on contractual salary, so a large sacrifice could reduce the mortgage you can borrow. Second, income-related benefits: statutory maternity pay, sick pay, and some employer benefits such as life cover are calculated on contractual salary. Third, state pension qualification: if sacrifice pushes your pay below the lower earnings limit (£6,396 in 2026/27), you may miss qualifying years — though this only affects very low earners.",
                    "For most employees in the middle of the earnings range, none of these edge cases apply. The tax saving is real, the pension benefit is real, and the only question is whether your employer operates a suitable scheme.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Salary sacrifice and the effects on pensions", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "HMRC: Income tax rates and allowances 2026/27", "url": "https://www.gov.uk/income-tax-rates"},
            {"label": "HMRC: National Insurance rates and categories", "url": "https://www.gov.uk/national-insurance-rates-letters"},
        ],
    },
    {
        "slug": "salary-sacrifice-pension-guide",
        "title": "Salary Sacrifice Pension: How It Works and Why It Beats a Personal Pension Contribution",
        "description": "Pension salary sacrifice is the most tax-efficient way for an employed person to save for retirement — but not all employers offer it. This guide covers how it works, the numbers, and what to ask your HR team.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "7 min read",
        "faqs": [
            {"q": "What is the difference between salary sacrifice and a normal pension contribution?", "a": "With a normal employee pension contribution, you pay from net salary and the pension provider reclaims basic-rate tax (relief at source) or your employer deducts from gross (net pay arrangement). Either way you still pay NI on the full salary. With salary sacrifice, the contribution never enters your salary — your gross pay is lower from the start, so you save both income tax and NI on the sacrificed amount."},
            {"q": "Does salary sacrifice pension affect the employer's contribution?", "a": "Not usually — your employer's contractual contribution is typically calculated as a percentage of your pensionable pay, which may be defined in your contract. However, some employers adjust the basis. Check your scheme documentation. Separately, many employers voluntarily add their NI saving on top of their contractual contribution."},
            {"q": "Is there an annual limit on salary sacrifice pension contributions?", "a": "The pension annual allowance of £60,000 (or 100% of earnings, whichever is lower) applies to all pension contributions combined — employee, employer, and any salary sacrifice amounts. Most employees are well below this limit. Only very high earners with large employer contributions need to track against it."},
        ],
        "sections": [
            {
                "heading": "How pension salary sacrifice differs from other contribution routes",
                "paragraphs": [
                    "There are three ways money can enter your pension with tax relief: salary sacrifice, net pay arrangement, and relief at source. Of these, salary sacrifice is the only one that also saves National Insurance. Under a net pay arrangement or relief at source scheme, your gross salary remains unchanged — you pay NI on the full amount before any pension relief is applied. Under salary sacrifice, your contractual salary is reduced by the contribution amount, so NI is charged on a smaller base.",
                    "For a basic-rate taxpayer, the NI saving on salary sacrifice is 8% of the contribution. On £3,000 per year that is £240 in NI — money you keep in addition to the income tax saving. For a higher-rate taxpayer earning above £50,270, the NI saving is 2% (the upper rate), but the 40% income tax saving is substantial.",
                ],
            },
            {
                "heading": "The employer NI saving — and how to claim it",
                "paragraphs": [
                    "Your employer also saves 15% secondary NI on every pound you sacrifice. On a £3,000 annual sacrifice the employer saves £450. Many employers direct some or all of this saving into your pension on top of their normal employer contribution. This is sometimes called NI matching or NI passthrough. If your employer offers it, you receive an enhanced pension contribution at zero extra cost to either party — it is funded entirely by the HMRC NI saving.",
                    "If your employer does not currently offer NI passthrough, it is worth asking HR explicitly. Providing concrete numbers often helps: 'If I sacrifice £3,000, you save £450 in NI — would you consider directing some of that into my pension?' The worst outcome is they say no; the best outcome is you get a meaningful pension boost at no cost to anyone.",
                ],
            },
            {
                "heading": "Worked example: comparing sacrifice vs standard contribution",
                "paragraphs": [
                    "An employee on £40,000 wants £2,400 per year in pension contributions. Option A: standard employee contribution via relief at source. HMRC adds 20% top-up, so £2,400 gross goes in. Employee pays £2,400 × (1 − 20%) = £1,920 net, but still pays NI on the full £40,000 salary. Option B: salary sacrifice of £2,400. Employee pays income tax and NI on £37,600 instead of £40,000. Income tax saving: £480. NI saving: £192. Total saving: £672. Net cost of the £2,400 pension contribution is just £1,728 — £192 less than the standard route for the same pension outcome.",
                    "The difference is the NI saving, which the standard route misses entirely. Over 20 years, assuming the same salary, that extra £192 per year amounts to £3,840 in cumulative NI savings — just from the choice of contribution route.",
                ],
            },
            {
                "heading": "Setting up salary sacrifice with your employer",
                "paragraphs": [
                    "To use salary sacrifice for pension contributions, your employer must operate a salary sacrifice scheme. If they do not currently offer one, suggest it to HR or payroll — the employer also benefits from NI savings on all participating staff, so there is a strong business case for running the scheme. If they already offer it, you typically need to sign a salary sacrifice agreement (a contract amendment) specifying the amount and start date.",
                    "Salary sacrifice contributions are shown on your payslip as a reduction in gross pay rather than as a pension deduction. Your P60 will show your reduced gross salary. This is normal and does not affect your personal tax calculation — HMRC only looks at the figures your employer reports, which already reflect the sacrifice.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Salary sacrifice and pensions", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "HMRC: Pension annual allowance", "url": "https://www.gov.uk/pension-annual-allowance"},
            {"label": "The Pensions Regulator: Salary sacrifice and auto-enrolment", "url": "https://www.thepensionsregulator.gov.uk/en/employers/new-staff/salary-sacrifice"},
        ],
    },
    {
        "slug": "electric-car-salary-sacrifice-guide",
        "title": "Electric Car Salary Sacrifice: A Practical Guide for Employees in 2026/27",
        "description": "EV salary sacrifice lets you drive a new electric car while paying income tax and NI on a lower salary. With the BiK rate at just 4% in 2026/27, the savings can be significant — here is what to check before signing up.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "8 min read",
        "faqs": [
            {"q": "Do I need to declare the EV on my Self Assessment?", "a": "If you complete Self Assessment (typically because you are a higher-rate taxpayer or have other untaxed income), you must declare the company car benefit. Your employer will report the P11D value and BiK rate to HMRC via a P11D form, and HMRC will adjust your tax code to collect the BiK tax through PAYE. Most employees on a basic salary sacrifice scheme do not need to do anything extra."},
            {"q": "What is included in the monthly sacrifice amount?", "a": "EV salary sacrifice schemes typically bundle the lease cost, insurance, maintenance, breakdown cover, and sometimes a charger installation. The exact package varies by provider. Road tax (VED) is currently zero for zero-emission vehicles. You should get a full breakdown from your employer's scheme administrator before agreeing to sacrifice."},
            {"q": "What if I leave my job mid-scheme?", "a": "Leaving employment typically triggers an early termination of the hire agreement. You may be liable for the remaining hire payments or an early exit fee, depending on your employer's scheme terms. Read the termination clause carefully before entering an EV salary sacrifice arrangement, particularly if you think there is any chance of changing jobs."},
        ],
        "sections": [
            {
                "heading": "Why the EV BiK rate makes salary sacrifice so attractive",
                "paragraphs": [
                    "The benefit-in-kind (BiK) rate for zero-emission electric cars is 4% of P11D value in 2026/27. Compared to a petrol car with 120g/km CO2 (BiK rate around 28%), this is strikingly low. The BiK tax you pay on an EV is tiny — a £40,000 EV generates a BiK charge of £40,000 × 4% × 20% = £320 per year for a basic-rate taxpayer, or £640 for a higher-rate taxpayer. Meanwhile, the salary sacrifice saves income tax and NI on the full monthly lease amount sacrificed.",
                    "The net result for most employees is that an EV through salary sacrifice costs significantly less than leasing the same car privately from after-tax income. The exact saving depends on the car's P11D value, the lease cost, and your income tax rate.",
                ],
            },
            {
                "heading": "Calculating the real monthly cost",
                "paragraphs": [
                    "To work out your actual monthly cost, you need to know the monthly sacrifice amount and then subtract the income tax and NI savings, then add back the BiK tax. Example: sacrifice of £500/month (£6,000/year) on a £38,000 P11D-value EV. Basic-rate taxpayer: income tax saving £6,000 × 20% = £1,200, NI saving £6,000 × 8% = £480. Total saving: £1,680. BiK tax: £38,000 × 4% × 20% = £304. Net annual cost: £6,000 − £1,680 + £304 = £4,624. Monthly: £385.",
                    "Without salary sacrifice, the same lease costing £500/month from after-tax income would actually cost more in gross terms — a basic-rate taxpayer would need to earn roughly £694/month gross to take home £500 after tax and NI. Salary sacrifice cuts that real cost to £385. The saving is £309 per month on a comparable after-tax lease.",
                ],
            },
            {
                "heading": "The BiK rate is rising — plan ahead",
                "paragraphs": [
                    "The zero-emission BiK rate increases each year: 4% in 2026/27, 5% in 2027/28, 7% in 2028/29, and 9% in 2029/30. If you are signing a 3 or 4-year lease today, your BiK tax will be higher in later years. For a £40,000 car, the BiK tax to a basic-rate taxpayer rises from £320/year in 2026/27 to £720/year in 2029/30. Still modest, but worth factoring into the total cost over the scheme period.",
                    "Even at 9%, the EV BiK rate is far below petrol car rates. The salary sacrifice NI saving does not depend on BiK rates at all — it is a function of the sacrificed amount. So EV salary sacrifice will remain cost-effective well into the 2030s, though the margin over private leasing will narrow slightly as BiK rates rise.",
                ],
            },
            {
                "heading": "What to check before signing up",
                "paragraphs": [
                    "Before agreeing to an EV salary sacrifice arrangement, verify: (1) Does the scheme include comprehensive insurance, or do you need separate cover? (2) What are the mileage limits, and what do excess miles cost? (3) What happens to the arrangement if you leave employment? (4) Will your post-sacrifice salary fall below any critical thresholds — NMW, mortgage commitments, or income-linked benefits? (5) Does the scheme use a salary sacrifice contract amendment, and have you received a copy?",
                    "Run the numbers using our salary sacrifice calculator, entering your salary and the monthly sacrifice amount. Compare the effective monthly cost against a like-for-like private lease. For most people in full-time employment with a stable income, EV salary sacrifice is one of the strongest financial benefits currently available in the UK employment market.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Company car tax BiK rates 2026 to 2029", "url": "https://www.gov.uk/government/publications/rates-and-allowances-hmrc-company-car-tax"},
            {"label": "HMRC: Salary sacrifice and the effects on pensions and benefits", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
            {"label": "OZEV: Electric vehicle salary sacrifice schemes", "url": "https://www.gov.uk/guidance/plug-in-car-van-and-motorcycle-grant"},
        ],
    },
    {
        "slug": "salary-sacrifice-student-loans",
        "title": "Salary Sacrifice and Student Loans: Can You Reduce Your Repayments?",
        "description": "Student loan repayments in the UK are calculated on gross income above a threshold — not taxable income. Salary sacrifice lowers your gross pay, which can reduce your repayment amount each month. Here is how it works.",
        "date": "22 May 2026",
        "date_iso": "2026-05-22",
        "reading_time": "6 min read",
        "faqs": [
            {"q": "Does pension salary sacrifice reduce student loan repayments?", "a": "Yes — pension salary sacrifice reduces your gross salary, which is the figure used to calculate student loan repayments. If your sacrificed amount brings your salary closer to the repayment threshold (£27,295 for Plan 2, £24,990 for Plan 1 in 2026/27), or over the threshold, your monthly repayments will decrease or stop entirely."},
            {"q": "What is the student loan repayment rate in 2026/27?", "a": "Plan 1 borrowers repay 9% of income above £24,990. Plan 2 borrowers repay 9% of income above £27,295. Postgraduate loan borrowers repay 6% of income above £21,000. Salary sacrifice reduces the income assessed, so a £2,000 sacrifice saves £180 per year in Plan 2 repayments (9% × £2,000) in addition to the income tax and NI savings."},
            {"q": "Is this a legitimate way to reduce student loan repayments?", "a": "Yes, it is entirely above board. HMRC and the Student Loans Company both use gross salary as reported by your employer on your payroll return. Salary sacrifice is a formal, HMRC-recognised arrangement. There is no avoidance involved — you are simply using a tax-efficient route that lowers your gross pay by making a genuine non-cash exchange."},
        ],
        "sections": [
            {
                "heading": "How student loan repayments interact with salary sacrifice",
                "paragraphs": [
                    "UK student loan repayments are collected through PAYE and calculated on the same gross salary figure used for income tax. The important distinction is that pension salary sacrifice reduces gross pay before both income tax and student loan deductions are calculated. This is different from personal pension contributions made through relief at source, which reduce taxable income but leave the student loan calculation unaffected.",
                    "Specifically: if you earn £32,000 and sacrifice £2,000, your gross pay for payroll purposes becomes £30,000. Your Plan 2 repayment is now 9% × (£30,000 − £27,295) = 9% × £2,705 = £243.45 per year, compared to 9% × (£32,000 − £27,295) = 9% × £4,705 = £423.45 without the sacrifice. Saving: £180 per year in student loan repayments — on top of the income tax and NI savings.",
                ],
            },
            {
                "heading": "Combined saving: the full picture",
                "paragraphs": [
                    "For an employee on Plan 2 with a basic-rate income tax position and earnings in the main NI band, every £1,000 of pension salary sacrifice saves approximately: £200 income tax (20%), £80 NI (8%), and £90 student loan (9%). Total saving: £370 per £1,000 sacrificed. The net cost to take-home pay is only £630 — meaning a £1,000 pension contribution effectively costs £630 in reduced take-home.",
                    "This triple saving (tax, NI, student loan) makes salary sacrifice particularly compelling for recent graduates. It is one of the few situations where contributing to a pension is financially dominant over virtually any alternative use of that money — you essentially receive a 59% immediate return (£1,000 contribution at a cost of £630).",
                ],
            },
            {
                "heading": "The threshold effect: reducing repayments to zero",
                "paragraphs": [
                    "If your salary is close to the student loan repayment threshold, salary sacrifice can eliminate repayments entirely. A Plan 2 borrower earning £29,000 who sacrifices £2,000 brings their assessed income to £27,000 — below the £27,295 threshold. Repayments stop completely. The income tax and NI savings on the £2,000 sacrifice make the pension contribution very cheap, and the additional student loan saving is a bonus.",
                    "This is worth modelling carefully if you are in the £28,000–£35,000 range. Use our calculator to see the combined monthly saving across income tax, NI, and student loan deductions. The three-way saving can be surprisingly large.",
                ],
            },
            {
                "heading": "Postgraduate loans",
                "paragraphs": [
                    "Postgraduate loan (PGL) repayments follow the same mechanics. Borrowers repay 6% of earnings above £21,000. Salary sacrifice reduces gross pay before PGL is assessed. Some employees carry both a Plan 2 undergraduate loan and a PGL — in this case salary sacrifice produces four separate savings: income tax, NI, Plan 2 repayment reduction, and PGL reduction. The combined saving rate for a basic-rate taxpayer with both loans is roughly 43% of each pound sacrificed, making pension sacrifice extremely cost-effective.",
                ],
            },
        ],
        "sources": [
            {"label": "HMRC: Student loan deductions — employer guidance", "url": "https://www.gov.uk/guidance/special-rules-for-student-loans"},
            {"label": "Student Loans Company: Repayment thresholds 2026/27", "url": "https://www.slc.co.uk/students-and-customers/loan-repayment/repayment-thresholds.aspx"},
            {"label": "HMRC: Salary sacrifice arrangements", "url": "https://www.gov.uk/salary-sacrifice-and-the-effects-on-pensions"},
        ],
    },
]

BLOG_BY_SLUG = {p["slug"]: p for p in BLOG_POSTS}


@app.route("/blog")
def blog_index():
    return render_template(
        "blog_index.html",
        **_ctx(
            title="Salary Sacrifice Guides UK 2026/27 | UKSalarySacrificeCalculator",
            meta_description="In-depth UK salary sacrifice guides covering pensions, electric cars, cycle to work, Scotland, childcare and employer NI savings.",
            canonical_url=SITE_URL + "/blog",
            posts=BLOG_POSTS,
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "Blog", "url": SITE_URL + "/blog"},
            ],
        ),
    )


@app.route("/blog/<slug>")
def blog_post_view(slug: str):
    post = BLOG_BY_SLUG.get(slug)
    if not post:
        abort(404)
    return render_template(
        "blog_post.html",
        **_ctx(
            title=post["title"],
            meta_description=post["description"],
            canonical_url=SITE_URL + f"/blog/{slug}",
            post=post,
            examples=[],
            article_faqs=post.get("faqs", []),
            reference_facts=None,
            sources=post.get("sources", []),
            breadcrumbs=[
                {"name": "Home", "url": SITE_URL + "/"},
                {"name": "Blog", "url": SITE_URL + "/blog"},
                {"name": post["title"], "url": SITE_URL + f"/blog/{slug}"},
            ],
        ),
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
