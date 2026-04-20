# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import frappe


def signature_portal_base():
	"""Public URL prefix for signing routes (matches website_route_rules)."""
	path = (getattr(frappe.local, "path", None) or "").strip("/")
	if path == "electronic_signature" or path.startswith("electronic_signature/"):
		return "/electronic_signature"
	return "/sign"
