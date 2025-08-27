# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def start_teams_call(phone_number, doctype, docname):
	print("starting call with", phone_number, doctype, docname)
