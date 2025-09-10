# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import re

import frappe


@frappe.whitelist()
def start_phone_call(phone_number, doctype, docname):
	print("starting call with", phone_number, doctype, docname)


PHONE_NUMBER_PATTERN = re.compile(
	r"^"
	r"(?:\+?1[\s\-\.]?)?"  # Optional country code (+1 or 1)
	r"(?:\([0-9]{3}\)|[0-9]{3})"  # Area code with or without parentheses
	r"[\s\-\.]?"  # Optional separator
	r"[0-9]{3}"  # First 3 digits
	r"[\s\-\.]?"  # Optional separator
	r"[0-9]{4}"  # Last 4 digits
	r"(?:"  # Optional extension group
	r"[\s,]*"  # Optional space or comma before extension
	r"(?:ext\.?|x)"  # Extension prefix (ext, ext., or x)
	r"[\s]?"  # Optional space
	r"[0-9]{1,6}"  # Extension number (1-6 digits)
	r")?"
	r"$",
	re.IGNORECASE,
)


def _validate_data_fields(self):
	# data_field options defined in frappe.model.data_field_options
	for phone_field in self.meta.get_phone_fields():
		phone = self.get(phone_field.fieldname)
		frappe.utils.validate_phone_number_with_country_code(phone, phone_field.fieldname)

	for data_field in self.meta.get_data_fields():
		data = self.get(data_field.fieldname)
		data_field_options = data_field.get("options")
		old_fieldtype = data_field.get("oldfieldtype")

		if old_fieldtype and old_fieldtype != "Data":
			continue

		if data_field_options == "Email":
			if (self.owner in frappe.STANDARD_USERS) and (data in frappe.STANDARD_USERS):
				continue
			for email_address in frappe.utils.split_emails(data):
				frappe.utils.validate_email_address(email_address, throw=True)

		if data_field_options == "Name":
			frappe.utils.validate_name(data, throw=True)

		if data_field_options == "Phone":
			validate_phone_number(data, throw=True)

		if data_field_options == "URL":
			if not data:
				continue

			frappe.utils.validate_url(data, throw=True)


def validate_phone_number(phone_number, throw=False):
	"""Returns True if valid phone number"""
	if not phone_number:
		return False

	phone_number = phone_number.strip()
	match = PHONE_NUMBER_PATTERN.match(phone_number)

	if not match and throw:
		frappe.throw(
			frappe._("{0} is not a valid Phone Number").format(phone_number),
			frappe.InvalidPhoneNumberError,
		)

	return bool(match)
