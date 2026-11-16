# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import json
from unittest.mock import patch

import frappe

from communications.communications.overrides.notification import CommunicationsNotification


def test_create_system_notification_uses_route_recipients():
	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Override Notification",
			"channel": "Slack DM",
			"subject": "Override Subject",
			"message": "{{ sendmail_subject }}",
			"send_system_notification": 1,
		}
	)
	doc = frappe.get_doc({"doctype": "User", "name": "Administrator", "email": "admin@example.com"})
	context = {"doc": doc}

	frappe.local.email_override_recipients = ["test@example.com"]
	frappe.local.email_override_subject = "Routed Subject"
	frappe.local.email_override_message = "Routed body"
	frappe.local.email_override_extra = {
		"notification_log_type": "Assignment",
		"notification_log": {"from_user": "admin@example.com"},
	}

	try:
		with patch(
			"communications.communications.overrides.notification.enqueue_create_notification"
		) as mock_enqueue:
			notification.create_system_notification(doc, context)

		mock_enqueue.assert_called_once()
		users, notification_doc = mock_enqueue.call_args[0]
		assert users == ["test@example.com"]
		assert notification_doc["type"] == "Assignment"
		assert notification_doc["subject"] == "Routed Subject"
		assert notification_doc["from_user"] == "admin@example.com"
		assert notification_doc["from_email_override"] is True
	finally:
		frappe.local.email_override_recipients = None
		frappe.local.email_override_subject = None
		frappe.local.email_override_message = None
		frappe.local.email_override_extra = None


def test_create_system_notification_skips_when_desk_log_exists():
	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Override Notification",
			"channel": "Slack DM",
			"subject": "Override Subject",
			"message": "{{ sendmail_subject }}",
			"send_system_notification": 1,
		}
	)
	doc = frappe.get_doc({"doctype": "User", "name": "Administrator", "email": "admin@example.com"})
	frappe.local.email_override_recipients = ["test@example.com"]
	frappe.local.email_override_subject = "Routed Subject"
	frappe.local.email_override_extra = {
		"desk_notification_exists": True,
		"notification_log_type": "Assignment",
	}

	try:
		with patch(
			"communications.communications.overrides.notification.enqueue_create_notification"
		) as mock_enqueue:
			notification.create_system_notification(doc, {"doc": doc})

		mock_enqueue.assert_not_called()
	finally:
		frappe.local.email_override_recipients = None
		frappe.local.email_override_subject = None
		frappe.local.email_override_extra = None


def test_create_system_notification_falls_back_to_recipients():
	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Doc Event Notification",
			"channel": "Slack DM",
			"subject": "Alert",
			"message": "Hello",
			"send_system_notification": 1,
		}
	)
	doc = frappe.get_doc({"doctype": "User", "name": "Administrator", "email": "admin@example.com"})
	context = {"doc": doc}

	with patch.object(
		CommunicationsNotification,
		"get_list_of_recipients",
		return_value=(["owner@example.com"], [], []),
	):
		with patch(
			"communications.communications.overrides.notification.enqueue_create_notification"
		) as mock_enqueue:
			notification.create_system_notification(doc, context)

	mock_enqueue.assert_called_once()
	users, _notification_doc = mock_enqueue.call_args[0]
	assert users == ["owner@example.com"]


def test_create_system_notification_omits_empty_attachments():
	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Empty Attachments",
			"channel": "Email",
			"subject": "Alert",
			"message": "Hello",
		}
	)
	doc = frappe.get_doc({"doctype": "User", "name": "Administrator", "email": "admin@example.com"})

	with patch.object(
		CommunicationsNotification,
		"get_list_of_recipients",
		return_value=(["owner@example.com"], [], []),
	):
		with patch.object(CommunicationsNotification, "get_attachment", return_value=[]):
			with patch(
				"communications.communications.overrides.notification.enqueue_create_notification"
			) as mock_enqueue:
				notification.create_system_notification(doc, {"doc": doc})

	assert mock_enqueue.call_args.args[1]["attached_file"] is None


def test_create_system_notification_serializes_attachment():
	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Attachment",
			"channel": "Email",
			"subject": "Alert",
			"message": "Hello",
		}
	)
	doc = frappe.get_doc({"doctype": "User", "name": "Administrator", "email": "admin@example.com"})
	attachment = {"doctype": "Material Request", "name": "SR-2026-00392", "print_format": "Standard"}

	with patch.object(
		CommunicationsNotification,
		"get_list_of_recipients",
		return_value=(["owner@example.com"], [], []),
	):
		with patch.object(CommunicationsNotification, "get_attachment", return_value=[attachment]):
			with patch(
				"communications.communications.overrides.notification.enqueue_create_notification"
			) as mock_enqueue:
				notification.create_system_notification(doc, {"doc": doc})

	assert json.loads(mock_enqueue.call_args.args[1]["attached_file"]) == attachment


def test_get_list_of_recipients_merges_hook_recipients():
	from frappe.email.doctype.notification.notification import Notification, get_context

	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Hook Recipients",
			"channel": "Slack DM",
			"document_type": "Sales Order",
			"event": "Submit",
			"subject": "Alert",
			"message": "Hello",
			"recipients": [
				{"receiver_by_document_field": "owner"},
				{"receiver_by_hook": "Test Hook"},
			],
		}
	)
	doc = frappe.get_doc(
		{
			"doctype": "User",
			"name": "Administrator",
			"email": "admin@example.com",
			"owner": "Administrator",
		}
	)
	context = get_context(doc)

	with patch.object(
		Notification, "get_list_of_recipients", return_value=(["owner@example.com"], [], [])
	):
		with patch(
			"communications.communications.overrides.notification.resolve_recipient_hook",
			return_value=["hook@example.com"],
		):
			recipients, cc, bcc = notification.get_list_of_recipients(doc, context)

	assert set(recipients) == {"owner@example.com", "hook@example.com"}
	assert cc == []
	assert bcc == []


def test_get_list_of_recipients_skips_hook_when_row_condition_false():
	from frappe.email.doctype.notification.notification import Notification, get_context

	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Hook Condition",
			"channel": "Slack DM",
			"document_type": "Sales Order",
			"event": "Submit",
			"subject": "Alert",
			"message": "Hello",
			"recipients": [{"receiver_by_hook": "Test Hook", "condition": "False"}],
		}
	)
	doc = frappe.get_doc({"doctype": "User", "name": "Administrator", "email": "admin@example.com"})
	context = get_context(doc)

	with patch.object(Notification, "get_list_of_recipients", return_value=([], [], [])):
		with patch(
			"communications.communications.overrides.notification.resolve_recipient_hook",
		) as mock_resolve:
			recipients, cc, bcc = notification.get_list_of_recipients(doc, context)

	mock_resolve.assert_not_called()
	assert recipients == []


def test_validate_rejects_unknown_receiver_by_hook():
	notification = CommunicationsNotification(
		{
			"doctype": "Notification",
			"name": "Test Unknown Hook",
			"channel": "Slack DM",
			"document_type": "Sales Order",
			"event": "Submit",
			"subject": "Alert",
			"message": "Hello",
			"recipients": [{"receiver_by_hook": "Not Registered"}],
		}
	)

	with patch(
		"communications.communications.notification_recipients.get_recipient_hooks",
		return_value={"Sales Team": "my_app.notifications.sales_order_team"},
	):
		try:
			notification.validate()
			assert False, "Expected validation error for unknown hook"
		except frappe.ValidationError:
			pass


def test_normalize_recipients_maps_user_to_email():
	from communications.communications.notification_recipients import normalize_recipients

	admin_email = frappe.db.get_value("User", "Administrator", "email")
	assert normalize_recipients(["Administrator"]) == [admin_email]
	assert normalize_recipients(["not-an-email", admin_email]) == [admin_email]


def test_resolve_recipient_hook_logs_and_returns_empty_on_error():
	from communications.communications.notification_recipients import resolve_recipient_hook

	notification = frappe._dict(log_error=lambda *args, **kwargs: None)
	doc = frappe._dict(doctype="Sales Order", name="SO-TEST")
	row = frappe._dict(receiver_by_hook="Broken Hook")
	context = {"doc": doc}

	with patch(
		"communications.communications.notification_recipients.get_recipient_hooks",
		return_value={"Broken Hook": "communications.tests.does_not_exist.hook"},
	):
		assert resolve_recipient_hook("Broken Hook", doc, notification, row, context) == []
