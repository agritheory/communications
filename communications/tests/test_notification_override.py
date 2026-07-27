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
	finally:
		frappe.local.email_override_recipients = None
		frappe.local.email_override_subject = None
		frappe.local.email_override_message = None
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
