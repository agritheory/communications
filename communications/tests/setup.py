# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.account.account import update_account_number
from erpnext.setup.utils import enable_all_roles_and_domains, set_defaults_for_tests
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

from frappe.utils.password import update_password

from communications.communications.install import create_default_notifications
from communications.tests.fixtures import employees, holidays, suppliers, tax_authority, users


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
	create_employees(settings)
	create_users(users)
	create_suppliers(settings)
	create_items(settings)
	add_holiday_lists()
	create_default_notifications()
	create_public_calendars()
	create_booked_event()
	dismiss_onboarding()


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
		"Account", "2000 - Source of Funds (Liabilities) - CFC", "2000 - Liabilities - CFC", force=True
	)
	frappe.rename_doc(
		"Account", "1310 - Debtors - CFC", "1310 - Accounts Receivable - CFC", force=True
	)
	frappe.rename_doc(
		"Account", "2110 - Creditors - CFC", "2110 - Accounts Payable - CFC", force=True
	)
	update_account_number("1110 - Cash - CFC", "Petty Cash", account_number="1110")
	update_account_number("Primary Checking - CFC", "Primary Checking", account_number="1201")


def create_public_calendars():
	if frappe.db.exists("Public Calendar", "dbenton"):
		return
	cal = frappe.get_doc(
		{
			"doctype": "Public Calendar",
			"title": "Darnell Benton",
			"user": "dbenton@cfc.co",
			"route": "dbenton",
			"enabled": 1,
			"is_public": 1,
			"allow_booking": 1,
			"notify_host_on_booking": 1,
			"notify_guest_on_booking": 1,
			"notify_on_cancellation": 1,
		}
	)
	cal.insert(ignore_permissions=True)


def create_booked_event():
	# Always recreate so tests start with a clean (non-Cancelled) event.
	existing = frappe.db.get_value(
		"Event", {"subject": "Test Appointment", "reference_docname": "dbenton"}, "name"
	)
	if existing:
		frappe.delete_doc("Event", existing, force=1, ignore_permissions=True)

	d = frappe.utils.add_days(frappe.utils.getdate(), 7)
	event = frappe.get_doc(
		{
			"doctype": "Event",
			"subject": "Test Appointment",
			"starts_on": f"{d} 10:00:00",
			"ends_on": f"{d} 11:00:00",
			"event_type": "Public",
			"reference_doctype": "Public Calendar",
			"reference_docname": "dbenton",
		}
	)
	event.append(
		"event_participants", {"reference_doctype": "User", "reference_docname": "dbenton@cfc.co"}
	)
	event.append(
		"event_participants", {"reference_doctype": "User", "reference_docname": "arivers@cfc.co"}
	)
	event.insert(ignore_permissions=True)


def create_employees(settings, only_create=None):
	for employee in employees:
		if only_create and employee.get("employee_name") not in only_create:
			continue

		if frappe.db.exists("Employee", {"employee_name": employee.get("employee_name")}):
			continue

		if not frappe.db.exists("Designation", employee.get("designation")):
			desg = frappe.new_doc("Designation")
			desg.designation_name = employee.get("designation")
			desg.save()

		empl = frappe.new_doc("Employee")
		empl.update(employee)
		empl.reports_to = None
		if settings.company:
			empl.company = settings.company
		empl.save()

		user = frappe.new_doc("User")
		user.email = f"{empl.first_name[0].lower()}{empl.last_name.lower()}@cfc.co"
		user.first_name = empl.first_name
		user.last_name = empl.last_name
		user.send_welcome_email = 0
		user.enabled = 1
		user.language = settings.language
		user.time_zone = settings.time_zone
		for r in employee.get("roles", []):
			user.append("roles", {"role": r})

		user.save()
		update_password(user.email, "Test@1234")
		empl.user_id = user.email
		if employee.get("reports_to"):
			empl.reports_to = frappe.get_value("Employee", {"employee_name": employee.get("reports_to")})
		empl.save()


def add_holiday_lists():
	for holiday_list in holidays:
		if frappe.db.exists("Holiday List", holiday_list.get("holiday_list_name")):
			continue
		hl = frappe.new_doc("Holiday List")
		hl.update(holiday_list)
		hl.save()


def create_suppliers(settings):
	for supplier in suppliers + tax_authority:
		biz = frappe.new_doc("Supplier")
		biz.supplier_name = supplier[0]
		biz.supplier_group = "Services"
		biz.country = "United States"
		biz.supplier_default_mode_of_payment = supplier[2]
		biz.currency = "USD"
		biz.default_price_list = "Standard Buying"
		biz.save()


def create_items(settings):
	for supplier in suppliers + tax_authority:
		item = frappe.new_doc("Item")
		item.item_code = item.item_name = supplier[1]
		item.item_group = "Services"
		item.stock_uom = "Nos"
		item.maintain_stock = 0
		item.is_sales_item, item.is_sub_contracted_item, item.include_item_in_manufacturing = 0, 0, 0
		item.grant_commission = 0
		item.is_purchase_item = 1
		item.append("supplier_items", {"supplier": supplier[0]})
		item.append(
			"item_defaults",
			{"company": settings.company, "default_warehouse": "", "default_supplier": supplier[0]},
		)
		item.save()


def create_users(users):
	for u in users:
		user = frappe.new_doc("User")
		user.email = u["email"]
		user.first_name = u["first_name"]
		user.last_name = u["last_name"]
		user.send_welcome_email = u["send_welcome_email"]
		user.enabled = u["enabled"]
		user.language = u["language"]
		user.time_zone = u["time_zone"]
		user.save()
		frappe.db.commit()

		role = frappe.new_doc("Has Role")
		role.parent = u["email"]
		role.parentfield = "roles"
		role.parenttype = "User"
		role.role = u["role"]
		role.save()
		frappe.db.commit()

		# Reset user_type to override "Website User" selection (doesn't work when set above)
		user = frappe.get_doc("User", u["email"])
		user.user_type = ""
		user.save()
		frappe.db.commit()


def dismiss_onboarding():
	for m in frappe.get_all("Module Onboarding"):
		frappe.db.set_value("Module Onboarding", m, "is_complete", 1)
