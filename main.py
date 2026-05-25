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


BLOG_POSTS = [
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
