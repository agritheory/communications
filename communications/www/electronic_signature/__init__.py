# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils.data import now_datetime


@frappe.whitelist()
def add_signature(electronic_signature_name, signature_data):
	if not electronic_signature_name or not signature_data:
		frappe.throw(_("Required information missing"))

	doc = frappe.get_doc("Electronic Signature", electronic_signature_name)
	if doc.status not in ("Out for Signature",):
		frappe.throw(_("This document is not open for signing."))

	user = frappe.session.user
	for row in doc.signers:
		if row.email == user and row.executed_at:
			frappe.throw(_("You have already signed this document."))

	signature_value = (
		signature_data if isinstance(signature_data, str) else json.dumps(signature_data)
	)

	signed = False
	for row in doc.signers:
		if row.email == user and not row.executed_at:
			row.signature = signature_value
			row.executed_at = now_datetime()
			signed = True
			break

	if not signed:
		frappe.throw(_("You are not authorized to sign this document."))

	if doc.signers and all(row.executed_at for row in doc.signers):
		doc.status = "Completed"

	doc.save(ignore_permissions=True)
	return {"success": True}
