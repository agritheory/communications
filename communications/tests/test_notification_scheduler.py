# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

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


def test_notification_scheduler_enabled():
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.save()

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

	WindowManager.get_window_data(user) 

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
			"assign_to": ["quincy@cfc.com"],
			"description": "Test assignment",
		}
	)

	queue_entries = frappe.get_all(
		"Assignment Notification Queue", filters={"reference_name": task.name}
	)
	assert len(queue_entries) == 1
	queue_entry = frappe.get_doc("Assignment Notification Queue", queue_entries[0].name)
	assert queue_entry.bypass_batching == 1
	assert queue_entry.status == "Sent"
