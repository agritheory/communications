# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import frappe


def communications_sendmail_log():
	from frappe.utils.logger import get_logger

	return get_logger(
		module="communications.sendmail",
		stream_only=True,
		allow_site=False,
	)


ROUTE_M_Q = re.compile(r"^M:(?P<mod>.+)\|Q:(?P<qual>[^\|]+)(\|L:(?P<ln>[0-9]+))?$")

ROUTE_PATH_Q = re.compile(r"^P:(?P<dots>.+)\|Q:(?P<qual>[^\|]+)(\|L:(?P<ln>[0-9]+))?$")


def generate_route_key_for_callable(obj: Callable[..., Any]) -> str:
	mod = getattr(obj, "__module__", "") or ""
	qual = getattr(obj, "__qualname__", None) or getattr(obj, "__name__", "") or ""
	if not mod or not qual:
		frappe.throw(frappe._("Callable has no module/qualname for route registration"))
	return f"M:{mod}|Q:{qual}"


def validate_route_key_or_throw(key: str) -> None:
	if not isinstance(key, str):
		frappe.throw(frappe._("Sendmail route key must be text"))
	s = key.strip()
	if not s:
		frappe.throw(frappe._("Sendmail route key is empty"))
	if not (s.startswith("M:") or s.startswith("P:") or s.startswith("T:") or s.startswith("S:")):
		frappe.throw(
			frappe._('Sendmail route key must start with one of prefixes "M:", "P:", "T:", or "S:".')
		)
	if s.startswith(("T:", "S:")):
		if len(s) <= 2 or not s[2:].strip():
			frappe.throw(frappe._("Route key payload after prefix is empty"))
		return
	if s.startswith("M:"):
		if not ROUTE_M_Q.match(s):
			frappe.throw(
				frappe._("M: route key must look like M:module.import.path|Q:qual.name or optional |L:123")
			)
		return
	if s.startswith("P:"):
		if not ROUTE_PATH_Q.match(s):
			frappe.throw(frappe._("P: route key must look like P:dotted.path|Q:qual or optional |L:123"))
		return
	frappe.throw(frappe._("Invalid sendmail route key"))


def validate_route_key_lenient_skip(key: str) -> bool:
	try:
		validate_route_key_or_throw(key)
	except Exception:
		return False
	return True


def collect_reference_sendmail_callsites():
	return [
		("frappe.desk.doctype.notification_log.notification_log.send_notification_email", None),
		("frappe.desk.notifications.notify_mentions", None),
		("erpnext.projects.doctype.project.project.Project.send_welcome_email", "erpnext"),
	]


def warm_reference_call_site_keys() -> None:
	log = communications_sendmail_log()
	try:
		installed = set(frappe.get_installed_apps() or [])
	except Exception:
		installed = set()

	for dotted, require_app in collect_reference_sendmail_callsites():
		if require_app and require_app not in installed:
			log.info("communications sendmail skipping %s (app %s not installed)", dotted, require_app)
			continue
		try:
			obj = frappe.get_attr(dotted)
			if not callable(obj):
				log.warning("communications sendmail %s not callable", dotted)
				continue
			rt = generate_route_key_for_callable(obj)
			validate_route_key_or_throw(rt)
			log.info("communications sendmail reference ok %s -> %s", dotted, rt)
		except Exception as e:
			log.warning("communications sendmail reference skip %s: %s", dotted, e)
