# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from communications.www.electronic_signature.portal_paths import signature_portal_base


def get_context(context):
	context.no_cache = 1
	context.title = _("Documents to sign")
	context.signature_base = signature_portal_base()
	context.guest = frappe.session.user == "Guest"
	context.signatures = []

	if context.guest:
		return context

	user = frappe.session.user
	user_type = frappe.db.get_value("User", user, "user_type")

	if user_type == "Website User":
		contact = frappe.db.get_value("Contact", {"user": user}, "name")
		if not contact:
			return context
		parent_names = frappe.get_all(
			"Electronic Signature Signer",
			filters={"contact": contact},
			pluck="parent",
			distinct=True,
		)
		if not parent_names:
			return context
		rows = frappe.get_all(
			"Electronic Signature",
			filters={
				"name": ["in", list(parent_names)],
				"status": ["in", ["Out for Signature", "Completed"]],
			},
			fields=["name", "title", "status", "reference_doctype", "reference_name", "modified"],
			order_by="modified desc",
		)
		print(rows)
		for row in rows:
			row["needs_signature"] = signer_row_needs_signature(row.name, contact)
		context.signatures = rows
		return context

	context.signatures = frappe.get_list(
		"Electronic Signature",
		filters={},
		fields=["name", "title", "status", "reference_doctype", "reference_name", "modified"],
		order_by="modified desc",
	)
	for row in context.signatures:
		row["needs_signature"] = False
	return context


def signer_row_needs_signature(parent, contact):
	signer_rows = frappe.get_all(
		"Electronic Signature Signer",
		filters={"parent": parent, "contact": contact},
		fields=["executed_at"],
	)
	return any(not r.executed_at for r in signer_rows)
