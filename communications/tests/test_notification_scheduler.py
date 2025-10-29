# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
from datetime import datetime

import frappe
from frappe.utils import today
from communications.communications.overrides.assignment import add as assign_user
from communications.notification_scheduler.window_manager import WindowManager


def test_notification_scheduler_disabled():
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 0
	config.save()

	supplier = frappe.get_all("Supplier", limit=1, pluck="name")[0]
	assign_user(
		{
			"doctype": "Supplier",
			"name": supplier,
			"assign_to": ["quincy@cfc.com"],
			"description": "Test assignment",
		}
	)
	queue_entries = frappe.get_all("Assignment Notification Queue")
	assert len(queue_entries) == 0


def _get_minutes_diff(window_data):
	window_start = datetime.fromisoformat(window_data["window_start"])
	window_end = datetime.fromisoformat(window_data["window_end"])
	diff_minutes = (window_end - window_start).total_seconds() / 60
	return diff_minutes


def test_notification_scheduler_enabled():
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.save()

	assert config.collection_window_minutes == 15
	assert config.delivery_start_hour == 8
	assert config.delivery_end_hour == 20

	supplier = frappe.get_all("Supplier", limit=2, pluck="name")[1]
	user = "quincy@cfc.com"

	assign_user(
		{"doctype": "Supplier", "name": supplier, "assign_to": [user], "description": "Test assignment"}
	)
	queue_entries = frappe.get_all("Assignment Notification Queue")
	assert len(queue_entries) == 1

	queue_entry = frappe.get_doc("Assignment Notification Queue", queue_entries[0])
	assert queue_entry.assigned_to == user
	assert queue_entry.status == "Queued"
	assert queue_entry.bypass_batching == 0
	assert queue_entry.notification_sent == 0
	assert str(queue_entry.assignment_date.date()) == today()
	assert queue_entry.window_key is not None

	frappe.db.commit()
	window_data = WindowManager.get_window_data(user)
	assert window_data.get("user") == user
	assert _get_minutes_diff(window_data) == config.collection_window_minutes


def test_priority_doctype_bypasses_batching():
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.bypass_batching_for_priority = 1
	config.priority_doctypes = "Task"
	config.save()

	task = frappe.get_doc({"doctype": "Task", "subject": "Test Task for Priority"}).insert()
	user = "quincy@cfc.com"
	assign_user(
		{
			"doctype": "Task",
			"name": task.name,
			"assign_to": [user],
			"description": "Test assignment",
		}
	)

	queue_entries = frappe.get_all(
		"Assignment Notification Queue", filters={"reference_name": task.name}
	)
	assert len(queue_entries) == 1
	queue_entry = frappe.get_doc("Assignment Notification Queue", queue_entries[0].name)
	assert queue_entry.bypass_batching == 1
	assert queue_entry.status == "Failed"

	frappe.db.commit()
	window_data = WindowManager.get_window_data(user)
	assert window_data.get("user") == user
	assert _get_minutes_diff(window_data) == config.collection_window_minutes

	error_log = frappe.get_last_doc("Error Log")
	assert (
		error_log.method
		== f"Error sending individual notification {queue_entry.name}: Please setup default outgoing Email Account from Tools > Email Account"
	)
