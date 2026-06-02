# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe


def invalidate_email_override_cache() -> None:
	frappe.cache.delete_value("communications:email_override_notifications")


def invalidate_email_override_cache_on_notification_change(doc, method=None):
	invalidate_email_override_cache()


def get_email_override_cache() -> dict[str, list[str]]:
	return frappe.cache.get_value(
		"communications:email_override_notifications",
		generator=build_email_override_cache,
	)


def build_email_override_cache() -> dict[str, list[str]]:
	cache: dict[str, list[str]] = {}
	if not frappe.db.has_column("Notification", "email_override"):
		return cache

	for row in frappe.get_all(
		"Notification",
		filters={"email_override": ["!=", ""], "enabled": 1},
		fields=["name", "email_override"],
		order_by="modified asc",
	):
		override = (row.email_override or "").strip()
		if override in (
			"Mention, Assignment, Share, Energy Point, Alert",
			"Document Follow",
			"Workflow Action",
			"Event Digest",
		):
			cache.setdefault(override, []).append(row.name)
	return cache


def notifications_for_override(override_value: str) -> list[str]:
	if override_value not in (
		"Mention, Assignment, Share, Energy Point, Alert",
		"Document Follow",
		"Workflow Action",
		"Event Digest",
	):
		return []
	return list(get_email_override_cache().get(override_value) or [])


def try_email_override(override_value: str, context_doc, kwargs: dict) -> bool:
	"""Dispatch enabled Notifications for this override; return True if stock email should be skipped."""
	notification_names = notifications_for_override(override_value)
	if not notification_names:
		return False

	set_email_override_state(kwargs)
	try:
		for notification_name in notification_names:
			frappe.get_doc("Notification", notification_name).send(context_doc)
	finally:
		clear_email_override_state()
	return True


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


def resolve_override_reference(kwargs: dict) -> tuple[str | None, str | None]:
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


def build_override_extra(kwargs: dict) -> dict[str, Any] | None:
	sendmail_args = kwargs.get("args") or {}
	extra: dict[str, Any] = {}

	if sendmail_args.get("docinfo") is not None:
		extra["docinfo"] = sendmail_args.get("docinfo")
	if sendmail_args.get("timeline") is not None:
		extra["timeline"] = sendmail_args.get("timeline")
	if sendmail_args.get("actions") is not None:
		extra["workflow_actions"] = list(sendmail_args.get("actions"))
	if sendmail_args.get("events") is not None:
		extra["events"] = sendmail_args.get("events")
	workflow_message = sendmail_args.get("message") or kwargs.get("message")
	if workflow_message:
		extra["workflow_message"] = workflow_message
	if kwargs.get("notification_log_type"):
		extra["notification_log_type"] = kwargs.get("notification_log_type")
	if kwargs.get("notification_log"):
		extra["notification_log"] = kwargs.get("notification_log")

	return extra or None


def set_email_override_state(kwargs: dict) -> None:
	raw_recipients = kwargs.get("recipients") or []
	if isinstance(raw_recipients, str):
		raw_recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]

	sendmail_args = kwargs.get("args") or {}
	sendmail_message = kwargs.get("message") or sendmail_args.get("description") or ""

	frappe.local.in_email_override = True
	frappe.local.email_override_recipients = normalize_route_recipients(list(raw_recipients))
	frappe.local.email_override_subject = kwargs.get("subject") or ""
	frappe.local.email_override_message = sendmail_message
	frappe.local.email_override_attachments = kwargs.get("attachments")
	frappe.local.email_override_extra = build_override_extra(kwargs)


def clear_email_override_state() -> None:
	frappe.local.in_email_override = False
	frappe.local.email_override_recipients = None
	frappe.local.email_override_subject = None
	frappe.local.email_override_message = None
	frappe.local.email_override_attachments = None
	frappe.local.email_override_extra = None
