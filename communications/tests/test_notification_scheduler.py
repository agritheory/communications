# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
from datetime import datetime

import frappe
from frappe.utils import today
from communications.communications.overrides.assignment import add as assign_user
from communications.notification_scheduler.window_manager import WindowManager

TEST_USER = "quincy@cfc.com"


def setup_function():
	"""Runs before each test: clear queue, Redis windows, and reset config to defaults."""
	frappe.db.delete("Assignment Notification Queue", {})
	frappe.db.delete("ToDo", {"allocated_to": TEST_USER, "status": "Open"})
	WindowManager.clear_window(TEST_USER)
	frappe.cache().delete_value("notification_window_settings")

	config = frappe.get_single("Notification Window Settings")
	config.enabled = 0
	config.collection_window_minutes = 15
	config.delivery_start_hour = 8
	config.delivery_end_hour = 20
	config.time_zone = "UTC"
	config.bypass_batching_for_priority = 0
	config.priority_doctypes = ""
	config.batch_template = ""
	config.individual_template = ""
	config.save()
	frappe.db.commit()


def get_minutes_diff(window_data):
	window_start = datetime.fromisoformat(window_data["window_start"])
	window_end = datetime.fromisoformat(window_data["window_end"])
	diff_minutes = (window_end - window_start).total_seconds() / 60
	return diff_minutes


def test_notification_scheduler_disabled():
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 0
	config.save()

	supplier = frappe.get_all("Supplier", limit=1, pluck="name")[0]
	assign_user(
		{
			"doctype": "Supplier",
			"name": supplier,
			"assign_to": [TEST_USER],
			"description": "Test assignment",
		}
	)
	queue_entries = frappe.get_all(
		"Assignment Notification Queue", filters={"assigned_to": TEST_USER}
	)
	assert len(queue_entries) == 0


def test_notification_scheduler_enabled():
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.save()

	assert config.collection_window_minutes == 15
	assert config.delivery_start_hour == 8
	assert config.delivery_end_hour == 20

	supplier = frappe.get_all("Supplier", limit=2, pluck="name")[1]

	assign_user(
		{
			"doctype": "Supplier",
			"name": supplier,
			"assign_to": [TEST_USER],
			"description": "Test assignment",
		}
	)
	queue_entries = frappe.get_all(
		"Assignment Notification Queue", filters={"assigned_to": TEST_USER}
	)
	assert len(queue_entries) == 1

	queue_entry = frappe.get_doc("Assignment Notification Queue", queue_entries[0])
	assert queue_entry.assigned_to == TEST_USER
	assert queue_entry.status == "Queued"
	assert queue_entry.bypass_batching == 0
	assert queue_entry.notification_sent == 0
	assert str(queue_entry.assignment_date.date()) == today()
	assert queue_entry.window_key is not None

	# Check window is in cache immediately — no commit needed for local cache read
	window_data = WindowManager.get_window_data(TEST_USER)
	assert window_data is not None
	assert window_data.get("user") == TEST_USER
	assert get_minutes_diff(window_data) == config.collection_window_minutes


def test_priority_doctype_bypasses_batching():
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.bypass_batching_for_priority = 1
	config.priority_doctypes = "Task"
	config.save()

	task = frappe.get_doc({"doctype": "Task", "subject": "Test Task for Priority"}).insert()
	assign_user(
		{
			"doctype": "Task",
			"name": task.name,
			"assign_to": [TEST_USER],
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

	# Window is still created by before_insert even for bypass path
	window_data = WindowManager.get_window_data(TEST_USER)
	assert window_data is not None
	assert window_data.get("user") == TEST_USER
	assert get_minutes_diff(window_data) == config.collection_window_minutes

	error_log = frappe.get_last_doc("Error Log")
	assert (
		error_log.method
		== f"Error sending individual notification {queue_entry.name}: Please setup default outgoing Email Account from Tools > Email Account"
	)
