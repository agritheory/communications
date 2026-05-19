# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

"""Helpers for frappe.sendmail route overrides. See docs/sendmail-routes.md."""

from __future__ import annotations

import ast
import json
from typing import Any

import frappe


def invalidate_sendmail_route_cache() -> None:
	import communications

	communications.sendmail_route_cache = None


def invalidate_sendmail_route_cache_on_notification_change(doc, method=None):
	if doc.get("sendmail_route_key"):
		invalidate_sendmail_route_cache()


def normalize_route_recipients(recipients: list) -> list[str]:
	"""Resolve User names to email addresses for Slack DM and other channels."""
	normalized: list[str] = []
	for recipient in recipients:
		if not recipient:
			continue
		value = str(recipient).strip()
		if not value:
			continue
		if "@" in value:
			normalized.append(value)
			continue
		user_email = frappe.db.get_value("User", value, "email")
		if user_email:
			normalized.append(user_email)
		else:
			normalized.append(value)
	return normalized


def parse_sendmail_route_match(raw: str | None) -> dict | None:
	if not raw or not str(raw).strip():
		return None
	try:
		parsed = json.loads(raw)
	except json.JSONDecodeError:
		try:
			parsed = ast.literal_eval(raw)
		except (ValueError, SyntaxError):
			return None
	if not isinstance(parsed, dict):
		return None
	return {str(k): v for k, v in parsed.items()}


def sendmail_route_payload(kwargs: dict) -> dict:
	payload = dict(getattr(frappe.local, "sendmail_route_context", None) or {})
	if kwargs.get("template"):
		payload["template"] = kwargs.get("template")
	return payload


def sendmail_route_matches(match: dict | None, payload: dict) -> bool:
	if not match:
		return True
	return all(payload.get(key) == value for key, value in match.items())


def resolve_sendmail_route_reference(kwargs: dict) -> tuple[str | None, str | None]:
	sendmail_args = kwargs.get("args") or {}
	ref_doctype = kwargs.get("reference_doctype") or sendmail_args.get("document_type")
	ref_name = kwargs.get("reference_name") or sendmail_args.get("document_name")
	if ref_doctype and ref_name:
		return ref_doctype, ref_name

	if kwargs.get("template") == "document_follow":
		docinfo = sendmail_args.get("docinfo") or []
		if docinfo:
			first = docinfo[0]
			return first.get("reference_doctype"), first.get("reference_docname")

	return None, None


def build_sendmail_route_extra(kwargs: dict) -> dict[str, Any] | None:
	sendmail_args = kwargs.get("args") or {}
	extra: dict[str, Any] = {}

	if sendmail_args.get("docinfo") is not None:
		extra["docinfo"] = sendmail_args.get("docinfo")
	if sendmail_args.get("timeline") is not None:
		extra["timeline"] = sendmail_args.get("timeline")
	if sendmail_args.get("actions") is not None:
		extra["workflow_actions"] = list(sendmail_args.get("actions"))
	workflow_message = sendmail_args.get("message") or kwargs.get("message")
	if workflow_message:
		extra["workflow_message"] = workflow_message

	return extra or None


def set_sendmail_route_state(kwargs: dict) -> None:
	raw_recipients = kwargs.get("recipients") or []
	if isinstance(raw_recipients, str):
		raw_recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]

	sendmail_args = kwargs.get("args") or {}
	sendmail_message = kwargs.get("message") or sendmail_args.get("description") or ""

	frappe.local.in_sendmail_route = True
	frappe.local.sendmail_route_recipients = normalize_route_recipients(list(raw_recipients))
	frappe.local.sendmail_route_subject = kwargs.get("subject") or ""
	frappe.local.sendmail_route_message = sendmail_message
	frappe.local.sendmail_route_attachments = kwargs.get("attachments")
	frappe.local.sendmail_route_extra = build_sendmail_route_extra(kwargs)


def clear_sendmail_route_state() -> None:
	frappe.local.in_sendmail_route = False
	frappe.local.sendmail_route_recipients = None
	frappe.local.sendmail_route_subject = None
	frappe.local.sendmail_route_message = None
	frappe.local.sendmail_route_attachments = None
	frappe.local.sendmail_route_extra = None


def build_sendmail_cache() -> dict[tuple[str, str], list[dict]]:
	if not frappe.db.has_column("Notification", "sendmail_route_key"):
		return {}
	fields = ["name", "sendmail_route_key"]
	if frappe.db.has_column("Notification", "sendmail_route_match"):
		fields.append("sendmail_route_match")
	notifications = frappe.get_all(
		"Notification",
		filters={"sendmail_route_key": ["!=", ""], "enabled": 1},
		fields=fields,
	)
	cache: dict[tuple[str, str], list[dict]] = {}
	for row in notifications:
		try:
			parsed = ast.literal_eval(row.sendmail_route_key)
		except (ValueError, SyntaxError):
			continue
		if not isinstance(parsed, (tuple, list)) or len(parsed) != 2:
			continue
		route_key = (str(parsed[0]), str(parsed[1]))
		cache.setdefault(route_key, []).append(
			{
				"name": row.name,
				"match": parse_sendmail_route_match(getattr(row, "sendmail_route_match", None)),
			}
		)
	return cache


def notifications_for_sendmail_route(
	cache: dict[tuple[str, str], list[dict]],
	route_key: tuple[str, str],
	kwargs: dict,
) -> list[str]:
	entries = cache.get(route_key) or []
	payload = sendmail_route_payload(kwargs)
	return [entry["name"] for entry in entries if sendmail_route_matches(entry.get("match"), payload)]
