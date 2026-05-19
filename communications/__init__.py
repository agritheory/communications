# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
#
# Sendmail route overrides: see communications/docs/sendmail-routes.md

__version__ = "15.6.0"

import inspect

import frappe

from communications.sendmail_routes import (
	build_sendmail_cache,
	clear_sendmail_route_state,
	notifications_for_sendmail_route,
	resolve_sendmail_route_reference,
	set_sendmail_route_state,
)

sendmail_route_cache = None


def call_site_key(depth: int = 2) -> tuple[str, str]:
	frame = inspect.currentframe()
	try:
		for __ in range(depth):
			frame = frame.f_back
			if frame is None:
				return ("<unknown>", "<unknown>")
		return (
			frame.f_globals.get("__name__", "<unknown>"),
			getattr(frame.f_code, "co_qualname", frame.f_code.co_name),
		)
	finally:
		del frame


def patch_send_notification_email() -> None:
	from frappe.desk.doctype.notification_log import notification_log as notification_log_module

	original = notification_log_module.send_notification_email

	def send_notification_email(doc):
		frappe.local.sendmail_route_context = {
			"notification_log_type": doc.type or "",
			"template": "new_notification",
		}
		try:
			return original(doc)
		finally:
			frappe.local.sendmail_route_context = None

	notification_log_module.send_notification_email = send_notification_email


def patch_sendmail() -> None:
	original = frappe.sendmail

	def override_sendmail(*args, **kwargs):
		global sendmail_route_cache
		if getattr(frappe.local, "in_sendmail_route", False):
			return original(*args, **kwargs)

		if sendmail_route_cache is None:
			sendmail_route_cache = build_sendmail_cache()

		route_key = call_site_key(depth=2)
		notification_names = notifications_for_sendmail_route(sendmail_route_cache, route_key, kwargs)
		if not notification_names:
			return original(*args, **kwargs)

		ref_doctype, ref_name = resolve_sendmail_route_reference(kwargs)
		if not (ref_doctype and ref_name):
			return original(*args, **kwargs)

		doc = frappe.get_doc(ref_doctype, ref_name)
		set_sendmail_route_state(kwargs)
		try:
			for notification_name in notification_names:
				frappe.get_doc("Notification", notification_name).send(doc)
		finally:
			clear_sendmail_route_state()
		return

	frappe.sendmail = override_sendmail


patch_send_notification_email()
patch_sendmail()
