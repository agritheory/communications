# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from communications.communications.doctype.electronic_signature.electronic_signature import (
	agent_debug_log,
)
from communications.www.electronic_signature.portal_paths import signature_portal_base


def get_context(context):
	context.no_cache = 1
	name = frappe.form_dict.name
	base = signature_portal_base()
	context.signature_base = base

	if not name:
		frappe.local.flags.redirect_location = base
		raise frappe.Redirect

	try:
		doc = frappe.get_doc("Electronic Signature", name)
	except frappe.DoesNotExistError:
		frappe.local.flags.redirect_location = base
		raise frappe.Redirect

	# #region agent log
	agent_debug_log(
		"H5_portal_detail",
		"www/electronic_signature/[name]/index.py:get_context",
		"before_doc_has_permission",
		{"doc": doc.name, "session_user": frappe.session.user},
	)
	# #endregion

	if not doc.has_permission("read"):
		# #region agent log
		agent_debug_log(
			"H5_portal_detail",
			"www/electronic_signature/[name]/index.py:get_context",
			"doc_has_permission_read_denied",
			{"doc": doc.name},
		)
		# #endregion
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	doc.add_viewed(user=frappe.session.user, force=True, unique_views=True)

	user = frappe.session.user
	contact = get_contact_from_user(user)
	contact_id = contact.name if contact else ""
	contact_name = contact.full_name if contact else ""

	active_signer_email = None
	if contact_id and doc.signers:
		for row in doc.signers:
			if row.contact == contact_id and not row.executed_at:
				active_signer_email = row.email
				break

	context.electronic_signature = doc
	context.active_signer_email = active_signer_email
	context.contact_id = contact_id
	context.contact_name = contact_name
	context.title = _("Sign") + ": " + (doc.title or doc.name)

	return context


def get_contact_from_user(user):
	contact_name = frappe.db.get_value("Contact", {"user": user})
	if contact_name:
		return frappe.get_doc("Contact", contact_name)
	return None
