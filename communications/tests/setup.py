# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.account.account import update_account_number
from erpnext.setup.utils import enable_all_roles_and_domains, set_defaults_for_tests
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete


def before_test():
    frappe.clear_cache()
    today = frappe.utils.getdate()
    setup_complete(
        {
            "currency": "USD",
            "full_name": "Administrator",
            "company_name": "Chelsea Fruit Co",
            "timezone": "America/New_York",
            "company_abbr": "CFC",
            "domains": ["Distribution"],
            "country": "United States",
            "fy_start_date": today.replace(month=1, day=1).isoformat(),
            "fy_end_date": today.replace(month=12, day=31).isoformat(),
            "language": "english",
            "company_tagline": "Chelsea Fruit Co",
            "email": "support@agritheory.dev",
            "password": "admin",
            "chart_of_accounts": "Standard with Numbers",
            "bank_account": "Primary Checking",
        }
    )
    enable_all_roles_and_domains()
    set_defaults_for_tests()
    frappe.db.commit()
    create_test_data()

    for modu in frappe.get_all("Module Onboarding"):
        frappe.db.set_value("Module Onboarding", modu, "is_complete", 1)
    frappe.set_value("Website Settings", "Website Settings", "home_page", "login")


def create_test_data():
    today = frappe.utils.getdate()
    setup_accounts()
    settings = frappe._dict(
        {
            "day": today.replace(month=1, day=1),
            "company": frappe.defaults.get_defaults().get("company"),
            "company_account": frappe.get_value(
                "Account",
                {
                    "account_type": "Bank",
                    "company": frappe.defaults.get_defaults().get("company"),
                    "is_group": 0,
                },
            ),
        }
    )
    create_company_address(settings)
    create_bank_and_bank_account(settings)


def create_company_address(settings):
    company_address = frappe.new_doc("Address")
    company_address.title = settings.company
    company_address.address_type = "Office"
    company_address.address_line1 = "67C Sweeny Street"
    company_address.city = "Chelsea"
    company_address.state = "MA"
    company_address.pincode = "89077"
    company_address.is_your_company_address = True
    company_address.append("links", {"link_doctype": "Company", "link_name": settings.company})
    company_address.save()


def create_bank_and_bank_account(settings):
    if not frappe.db.exists("Bank", "Local Bank"):
        bank = frappe.new_doc("Bank")
        bank.bank_name = "Local Bank"
        bank.aba_number = "07200091"
        bank.save()

    if not frappe.db.exists("Bank Account", "Primary Checking - Local Bank"):
        bank_account = frappe.new_doc("Bank Account")
        bank_account.account_name = "Primary Checking"
        bank_account.bank = bank.name
        bank_account.is_default = 1
        bank_account.is_company_account = 1
        bank_account.company = settings.company
        bank_account.account = settings.company_account
        bank_account.check_number = 2500
        bank_account.company_ach_id = "1381655417"
        bank_account.bank_account_no = "072000915"
        bank_account.branch_code = "07200091"
        bank_account.save()

    doc = frappe.new_doc("Journal Entry")
    doc.posting_date = settings.day
    doc.voucher_type = "Opening Entry"
    doc.company = settings.company
    opening_balance = 50000.00
    doc.append(
        "accounts",
        {"account": settings.company_account, "debit_in_account_currency": opening_balance},
    )
    retained_earnings = frappe.get_value(
        "Account", {"account_name": "Retained Earnings", "company": settings.company}
    )
    doc.append(
        "accounts", {"account": retained_earnings, "credit_in_account_currency": opening_balance}
    )
    doc.save()
    doc.submit()


def setup_accounts():
    frappe.rename_doc(
        "Account", "1000 - Application of Funds (Assets) - CFC", "1000 - Assets - CFC", force=True
    )
    frappe.rename_doc(
        "Account",
        "2000 - Source of Funds (Liabilities) - CFC",
        "2000 - Liabilities - CFC",
        force=True,
    )
    frappe.rename_doc(
        "Account", "1310 - Debtors - CFC", "1310 - Accounts Receivable - CFC", force=True
    )
    frappe.rename_doc(
        "Account", "2110 - Creditors - CFC", "2110 - Accounts Payable - CFC", force=True
    )
    update_account_number("1110 - Cash - CFC", "Petty Cash", account_number="1110")
    update_account_number("Primary Checking - CFC", "Primary Checking", account_number="1201")
