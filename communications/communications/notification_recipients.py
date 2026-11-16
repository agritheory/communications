# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import validate_email_address


def get_recipient_hooks() -> dict[str, str]:
	"""Map hook title (stored on recipient row) to dotted path of the resolver function."""
	raw = frappe.get_hooks("notification_recipients") or {}
	resolved = {}
	for key, paths in raw.items():
		if not paths:
			continue
		path = paths[-1] if isinstance(paths, list) else paths
		if path:
			resolved[key] = path
	return resolved


def normalize_recipients(values) -> list[str]:
	if not values:
		return []
	if isinstance(values, str):
		values = [values]
	out = []
	seen = set()
	for value in values:
		if not value:
			continue
		value = value.strip()
		if not value:
			continue
		if validate_email_address(value):
			email = value
		elif frappe.db.exists("User", value):
			email = frappe.db.get_value("User", value, "email")
		else:
			continue
		if email and validate_email_address(email) and email not in seen:
			seen.add(email)
			out.append(email)
	return out


def resolve_recipient_hook(key, doc, notification, row, context) -> list[str]:
	hooks = get_recipient_hooks()
	path = hooks.get(key)
	if not path:
		return []
	try:
		fn = frappe.get_attr(path)
		result = fn(doc, notification, row, context)
	except Exception as e:
		notification.log_error(f"Receiver By Hook {key!r} failed", e)
		return []
	return normalize_recipients(result)


@frappe.whitelist()
def get_recipient_hook_options() -> list[str]:
	frappe.only_for("System Manager")
	return sorted(get_recipient_hooks().keys())


def validate_recipient_hook_keys(notification) -> None:
	registered = get_recipient_hooks()
	for row in notification.recipients or []:
		key = row.get("receiver_by_hook")
		if key and key not in registered:
			frappe.throw(
				frappe._("Unknown Receiver By Hook {0}. Registered hooks: {1}").format(
					frappe.bold(key),
					", ".join(sorted(registered.keys())) or frappe._("(none)"),
				)
			)
