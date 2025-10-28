import datetime

import frappe
from erpnext.setup.utils import enable_all_roles_and_domains, set_defaults_for_tests
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

from communications.tests.fixtures import suppliers, tax_authority, users


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


def create_test_data():
	settings = frappe._dict(
		{
			"day": datetime.date(
				int(frappe.defaults.get_defaults().get("fiscal_year", datetime.datetime.now().year)), 1, 1
			),
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

	create_users(users)
	create_suppliers(settings)
	create_items(settings)
	dismiss_onboarding()


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
