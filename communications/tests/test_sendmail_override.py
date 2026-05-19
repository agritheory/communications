# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
import pytest

import communications as comm
from communications.communications.overrides.notification import (
	CommunicationsNotification,
)
from communications.sendmail_routes import normalize_route_recipients
from communications.tests.sendmail_route_keys import (
	DOCUMENT_FOLLOW_ROUTE_KEY,
	NOTIFICATION_LOG_ROUTE_KEY,
	WORKFLOW_ACTION_ROUTE_KEY,
)

SENDMAIL_ROUTE_NOTIFICATION = "Communications \u2014 Notification Log email (sendmail route)"
WORKFLOW_ROUTE_NOTIFICATION = "Communications \u2014 Workflow action email (sendmail route)"
DOCUMENT_FOLLOW_ROUTE_NOTIFICATION = "Communications \u2014 Document Follow email (sendmail route)"
TEST_ROUTE_KEY = (
	"communications.tests.test_sendmail_override",
	"invoke_from_test_route",
)


def invoke_from_test_route(todo_name: str) -> None:
	"""Module-level caller whose identity matches TEST_ROUTE_KEY in the override cache."""
	frappe.sendmail(
		recipients=["arivers@cfc.co"],
		subject="Test sendmail route interception",
		template="new_notification",
		args={"document_type": "ToDo", "document_name": todo_name},
		now=True,
	)


@pytest.mark.order(1)
def test_build_sendmail_cache_includes_notification_log_route():
	"""Cache built from the DB contains the fixture notification under the expected call-site key."""
	cache = comm.build_sendmail_cache()
	assert (
		NOTIFICATION_LOG_ROUTE_KEY in cache
	), f"Expected {NOTIFICATION_LOG_ROUTE_KEY!r} in cache; got keys: {list(cache.keys())}"
	names = [entry["name"] for entry in cache[NOTIFICATION_LOG_ROUTE_KEY]]
	assert SENDMAIL_ROUTE_NOTIFICATION in names


@pytest.mark.order(1)
def test_build_sendmail_cache_includes_workflow_and_document_follow_routes():
	cache = comm.build_sendmail_cache()
	assert WORKFLOW_ACTION_ROUTE_KEY in cache
	assert DOCUMENT_FOLLOW_ROUTE_KEY in cache
	workflow_names = [entry["name"] for entry in cache[WORKFLOW_ACTION_ROUTE_KEY]]
	follow_names = [entry["name"] for entry in cache[DOCUMENT_FOLLOW_ROUTE_KEY]]
	assert WORKFLOW_ROUTE_NOTIFICATION in workflow_names
	assert DOCUMENT_FOLLOW_ROUTE_NOTIFICATION in follow_names


@pytest.mark.order(1)
def test_notifications_for_sendmail_route_filters_by_match():
	cache = {
		TEST_ROUTE_KEY: [
			{"name": "Broad", "match": None},
			{"name": "Mention only", "match": {"notification_log_type": "Mention"}},
		]
	}
	kwargs = {"template": "new_notification"}
	assert comm.notifications_for_sendmail_route(cache, TEST_ROUTE_KEY, kwargs) == ["Broad"]

	frappe.local.sendmail_route_context = {
		"notification_log_type": "Mention",
		"template": "new_notification",
	}
	try:
		assert comm.notifications_for_sendmail_route(cache, TEST_ROUTE_KEY, kwargs) == [
			"Broad",
			"Mention only",
		]
		frappe.local.sendmail_route_context = {"notification_log_type": "Assignment"}
		assert comm.notifications_for_sendmail_route(cache, TEST_ROUTE_KEY, kwargs) == ["Broad"]
	finally:
		frappe.local.sendmail_route_context = None


@pytest.mark.order(1)
def test_password_reset_call_site_does_not_match_notification_log_route():
	"""User password emails use a different module; they are not routed unless explicitly configured."""
	user_reset_key = ("frappe.core.doctype.user.user", "reset_password")
	cache = comm.build_sendmail_cache()
	assert user_reset_key not in cache


@pytest.mark.order(2)
def test_build_sendmail_cache_skips_malformed_route_key():
	"""A Notification row with an unparsable route key is silently excluded from the cache."""
	bad_name = "Sendmail Route Bad Key Test"
	if frappe.db.exists("Notification", bad_name):
		frappe.delete_doc("Notification", bad_name, force=True, ignore_permissions=True)

	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": bad_name,
			"enabled": 1,
			"is_standard": 0,
			"channel": "Email",
			"subject": "Test",
			"event": "Save",
			"document_type": "ToDo",
			"message": "Test",
			"sendmail_route_key": "not valid python",
		}
	).insert(ignore_permissions=True)

	try:
		cache = comm.build_sendmail_cache()
		for notification_names in cache.values():
			assert bad_name not in notification_names
	finally:
		frappe.delete_doc("Notification", bad_name, force=True, ignore_permissions=True)


@pytest.mark.order(3)
def test_call_site_key_identifies_module_and_function():
	"""call_site_key(depth=1) returns the calling function's module and qualified name."""
	result = comm.call_site_key(depth=1)
	assert result[0] == "communications.tests.test_sendmail_override"
	assert result[1] == "test_call_site_key_identifies_module_and_function"


@pytest.mark.order(4)
def test_sendmail_override_routes_from_configured_call_site():
	"""
	When frappe.sendmail is called from invoke_from_test_route, the override dispatches
	to CommunicationsNotification.send instead of falling through to the original sendmail.
	"""
	test_notification_name = "Sendmail Override Routing Test"
	if frappe.db.exists("Notification", test_notification_name):
		frappe.delete_doc("Notification", test_notification_name, force=True, ignore_permissions=True)

	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": test_notification_name,
			"enabled": 1,
			"is_standard": 0,
			"channel": "Email",
			"subject": "{{ doc.description or doc.name }}",
			"event": "Save",
			"document_type": "ToDo",
			"message": "<p>{{ doc.description or '' }}</p>",
			"sendmail_route_key": repr(TEST_ROUTE_KEY),
		}
	).insert(ignore_permissions=True)

	todo = frappe.get_doc(
		{
			"doctype": "ToDo",
			"description": "Sendmail override routing test",
			"allocated_to": "Administrator",
		}
	).insert(ignore_permissions=True)

	comm.sendmail_route_cache = None

	send_calls = []

	def tracking_send(self, doc):
		send_calls.append(self.name)

	try:
		with patch.object(CommunicationsNotification, "send", tracking_send):
			invoke_from_test_route(todo.name)
	finally:
		frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Notification", test_notification_name, force=True, ignore_permissions=True)
		comm.sendmail_route_cache = None

	assert len(send_calls) == 1, f"Expected 1 Notification.send call; got {send_calls!r}"
	assert send_calls[0] == test_notification_name


@pytest.mark.order(5)
def test_normalize_route_recipients_resolves_user_name_to_email():
	admin_email = frappe.db.get_value("User", "Administrator", "email")
	assert normalize_route_recipients(["Administrator"]) == [admin_email]
	assert normalize_route_recipients([admin_email]) == [admin_email]


@pytest.mark.order(5)
def test_resolve_sendmail_route_reference_document_follow():
	kwargs = {
		"template": "document_follow",
		"args": {
			"docinfo": [
				{
					"reference_doctype": "ToDo",
					"reference_docname": "TODO-TEST-1",
					"reference_url": "/app/todo/TODO-TEST-1",
				}
			],
			"timeline": [{"time": "2026-01-01", "message": "test"}],
		},
	}
	assert comm.resolve_sendmail_route_reference(kwargs) == ("ToDo", "TODO-TEST-1")


@pytest.mark.order(6)
def test_sendmail_override_routes_workflow_action_email():
	test_notification_name = WORKFLOW_ROUTE_NOTIFICATION
	if not frappe.db.exists("Notification", test_notification_name):
		pytest.skip(f"Fixture notification {test_notification_name!r} not installed")

	todo = frappe.get_doc(
		{"doctype": "ToDo", "description": "Workflow route test", "allocated_to": "Administrator"}
	).insert(ignore_permissions=True)

	comm.sendmail_route_cache = None
	send_calls = []

	def tracking_send(self, doc):
		send_calls.append((self.name, doc.doctype, doc.name))

	try:
		with (
			patch.object(comm, "call_site_key", return_value=WORKFLOW_ACTION_ROUTE_KEY),
			patch.object(CommunicationsNotification, "send", tracking_send),
		):
			frappe.sendmail(
				recipients=["arivers@cfc.co"],
				subject="Workflow on ToDo: test",
				template="workflow_action",
				message="<p>Please approve</p>",
				args={
					"actions": [{"action_name": "Approve", "action_link": "http://example.com/approve"}],
					"message": "<p>Please approve</p>",
				},
				reference_doctype="ToDo",
				reference_name=todo.name,
				attachments=[],
				now=True,
			)
	finally:
		frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)
		comm.sendmail_route_cache = None

	assert len(send_calls) == 1
	assert send_calls[0][0] == test_notification_name
	assert send_calls[0][1:] == ("ToDo", todo.name)


@pytest.mark.order(7)
def test_sendmail_override_routes_document_follow_email():
	test_notification_name = DOCUMENT_FOLLOW_ROUTE_NOTIFICATION
	if not frappe.db.exists("Notification", test_notification_name):
		pytest.skip(f"Fixture notification {test_notification_name!r} not installed")

	todo = frappe.get_doc(
		{"doctype": "ToDo", "description": "Document follow route test", "allocated_to": "Administrator"}
	).insert(ignore_permissions=True)

	comm.sendmail_route_cache = None
	send_calls = []

	def tracking_send(self, doc):
		send_calls.append((self.name, doc.doctype, doc.name))

	try:
		with (
			patch.object(comm, "call_site_key", return_value=DOCUMENT_FOLLOW_ROUTE_KEY),
			patch.object(CommunicationsNotification, "send", tracking_send),
		):
			frappe.sendmail(
				recipients=["arivers@cfc.co"],
				subject="Document Follow Notification",
				template="document_follow",
				args={
					"docinfo": [
						{
							"reference_doctype": "ToDo",
							"reference_docname": todo.name,
							"reference_url": f"/app/todo/{todo.name}",
						}
					],
					"timeline": [{"time": "2026-01-01", "message": "Field changed"}],
				},
				now=True,
			)
	finally:
		frappe.delete_doc("ToDo", todo.name, force=True, ignore_permissions=True)
		comm.sendmail_route_cache = None

	assert len(send_calls) == 1
	assert send_calls[0][0] == test_notification_name
	assert send_calls[0][1:] == ("ToDo", todo.name)
