# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

"""
Electronic signature invitations and magic login links.

``get_magic_link`` builds a one-time login URL when **Login with Email Link** is enabled
in System Settings. For the link to land on the signing page after login, the site must
honor the ``redirect-to`` query parameter on the login-key handler. Frappe core may not
apply that redirect; washmoreerp implements this by overriding
``frappe.www.login.login_via_key``. Sites using the signing portal can copy that pattern
into their own app if needed.
"""

import json
from urllib.parse import quote

import frappe
from frappe import _
from frappe.www.login import _generate_temporary_login_link


def get_magic_link(email, redirect_to=None):
	if not frappe.get_system_settings("login_with_email_link"):
		return ""
	expiry = frappe.get_system_settings("login_with_email_link_expiry") or 10
	link = _generate_temporary_login_link(email, expiry)
	if redirect_to:
		sep = "&" if "?" in link else "?"
		link = f"{link}{sep}redirect-to={quote(redirect_to)}"
	return link


@frappe.whitelist()
def fetch_signature_invitation_email(doc, recipient):
	doc = frappe._dict(json.loads(doc)) if isinstance(doc, str) else doc
	full = frappe.get_doc("Electronic Signature", doc.name)
	template_name = "Electronic Signature Request"
	if not frappe.db.exists("Email Template", template_name):
		frappe.throw(_("Email Template {0} not found").format(template_name))
	template = frappe.get_doc("Email Template", template_name)
	formatted = template.get_formatted_email(full.as_dict())
	redirect_path = f"/sign/{full.name}"
	magic_link = get_magic_link(recipient, redirect_to=redirect_path)
	message = formatted["message"].replace("\n", "<br>").replace("MAGIC_LINK", magic_link or "")
	return {
		"recipients": recipient,
		"subject": formatted["subject"],
		"email_message": message,
	}
