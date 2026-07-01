# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
import pytest

from communications.communications.email_override_defaults import NOTIFICATION_LOG_OVERRIDE
from communications.communications.email_overrides import (
	build_email_override_cache,
	invalidate_email_override_cache,
)
from communications.communications.overrides.assignment import add as assign_user

ASSIGNEE = "quincy@cfc.com"
ASSIGNER = "arivers@cfc.co"
NOTIFICATION_LOG_OVERRIDE_KEY = "Mention, Assignment, Share, Energy Point, Alert"


def enable_notification_log_override():
	frappe.db.set_value("Notification", NOTIFICATION_LOG_OVERRIDE, "enabled", 1)
	invalidate_email_override_cache()


def disable_notification_log_override():
	frappe.db.set_value("Notification", NOTIFICATION_LOG_OVERRIDE, "enabled", 0)
	invalidate_email_override_cache()


@pytest.mark.order(1)
def test_notification_log_override_fixture_is_installed():
	"""Starter row for desk Notification Log emails is seeded disabled on site setup."""
	assert frappe.db.exists("Notification", NOTIFICATION_LOG_OVERRIDE)
	row = frappe.db.get_value(
		"Notification",
		NOTIFICATION_LOG_OVERRIDE,
		["email_override", "enabled", "channel"],
		as_dict=True,
	)
	assert row.email_override == NOTIFICATION_LOG_OVERRIDE_KEY
	assert row.channel == "Email"
	assert row.enabled == 0


@pytest.mark.order(2)
def test_email_override_cache_includes_enabled_notification_log_override():
	enable_notification_log_override()
	try:
		cache = build_email_override_cache()
		assert NOTIFICATION_LOG_OVERRIDE in cache.get(NOTIFICATION_LOG_OVERRIDE_KEY, [])
	finally:
		disable_notification_log_override()


@pytest.mark.order(3)
def test_assignment_routes_through_notification_log_override():
	"""Assignment Notification Log email is handled by the override Notification, not stock template sendmail."""
	from frappe.desk.doctype.notification_log.notification_log import send_notification_email

	supplier = frappe.db.get_value("Supplier", {"supplier_name": "Exceptional Grid"})
	enable_notification_log_override()
	sendmail_calls = []

	def capture_sendmail(*args, **kwargs):
		sendmail_calls.append(kwargs)

	try:
		log = frappe.get_doc(
			{
				"doctype": "Notification Log",
				"type": "Assignment",
				"document_type": "Supplier",
				"document_name": supplier,
				"subject": "Assignment on Supplier Exceptional Grid",
				"email_content": "<p>Review the electricity bill submission.</p>",
				"from_user": ASSIGNER,
				"for_user": ASSIGNEE,
			}
		)

		with patch("frappe.sendmail", side_effect=capture_sendmail):
			send_notification_email(log)

		stock_calls = [call for call in sendmail_calls if call.get("template") == "new_notification"]
		override_calls = [call for call in sendmail_calls if call.get("template") != "new_notification"]

		assert not stock_calls
		assert len(override_calls) == 1
		assert override_calls[0]["recipients"] == [ASSIGNEE]
		assert "Review the electricity bill submission" in override_calls[0]["message"]
		assert "Assignment on Supplier Exceptional Grid" in override_calls[0]["message"]
	finally:
		disable_notification_log_override()


@pytest.mark.order(4)
def test_supplier_assignment_uses_notification_log_override():
	"""Arden assigns Exceptional Grid to Quincy; stock Notification Log template sendmail is skipped."""
	supplier = frappe.db.get_value("Supplier", {"supplier_name": "Exceptional Grid"})
	enable_notification_log_override()
	sendmail_calls = []

	def capture_sendmail(*args, **kwargs):
		sendmail_calls.append(kwargs)

	try:
		frappe.set_user(ASSIGNER)
		with patch("frappe.sendmail", side_effect=capture_sendmail):
			assign_user(
				{
					"doctype": "Supplier",
					"name": supplier,
					"assign_to": [ASSIGNEE],
					"description": "Confirm Q2 utility billing",
				}
			)

		stock_calls = [call for call in sendmail_calls if call.get("template") == "new_notification"]
		override_calls = [call for call in sendmail_calls if call.get("template") != "new_notification"]

		assert not stock_calls
		assert override_calls
		assert any(
			"Confirm Q2 utility billing" in (call.get("message") or "") for call in override_calls
		)
	finally:
		frappe.set_user("Administrator")
		disable_notification_log_override()
		frappe.db.delete(
			"ToDo",
			{
				"reference_type": "Supplier",
				"reference_name": supplier,
				"allocated_to": ASSIGNEE,
				"status": "Open",
			},
		)
