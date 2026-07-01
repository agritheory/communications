# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now_datetime, today
from communications.communications.overrides.assignment import add as assign_user
from communications.notification_scheduler.window_manager import WindowManager
from communications.notification_scheduler.batch_processor import (
	BatchProcessor,
	DeliveryRestrictions,
)
from communications.notification_scheduler.background_jobs import cleanup_old_queue_entries
from communications.communications.email_overrides import invalidate_email_override_cache

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


def force_expire_window(user):
	"""Set the window_end to the past to simulate an expired window."""
	window_data = WindowManager.get_window_data(user)
	assert window_data, "No window data found to expire"
	window_data["window_end"] = (now_datetime() - timedelta(minutes=1)).isoformat()
	WindowManager.set_window_data(user, window_data)
	return window_data


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


def test_multiple_assignments_share_window_key():
	"""Two assignments within the collection window get the same window_key and the
	notification_count in Redis is incremented for each."""
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.save()

	suppliers = frappe.get_all("Supplier", limit=2, pluck="name")
	assign_user(
		{"doctype": "Supplier", "name": suppliers[0], "assign_to": [TEST_USER], "description": "first"}
	)
	assign_user(
		{"doctype": "Supplier", "name": suppliers[1], "assign_to": [TEST_USER], "description": "second"}
	)

	entries = frappe.get_all(
		"Assignment Notification Queue",
		filters={"assigned_to": TEST_USER},
		fields=["name", "window_key"],
	)
	assert len(entries) == 2
	assert entries[0].window_key == entries[1].window_key

	window_data = WindowManager.get_window_data(TEST_USER)
	assert window_data is not None
	assert window_data["notification_count"] == 2


def test_priority_doctype_bypasses_batching():
	"""Priority doctypes bypass batching: the queue entry is created with bypass_batching=1
	and send_individual_notification is called immediately. When the send fails the status
	must be 'Failed' and an error must be logged — regardless of whether a mail server is
	configured in site_config."""
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.bypass_batching_for_priority = 1
	config.priority_doctypes = "Task"
	config.save()

	task = frappe.get_doc({"doctype": "Task", "subject": "Test Task for Priority"}).insert()

	# Patch frappe.sendmail to raise and try_email_override to return False so the full
	# dispatcher failure-handling path runs (status -> "Failed", error logged) regardless
	# of whether a real mail server is configured in site_config.
	with patch("frappe.sendmail", side_effect=Exception("Simulated send failure")), patch(
		"communications.notification_scheduler.dispatcher.try_email_override", return_value=False
	):
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
	assert error_log.method.startswith(f"Error sending individual notification {queue_entry.name}:")


def test_batch_processor_processes_expired_window():
	"""When a window expires, process_expired_windows marks queue entries Sent or Failed
	and clears the Redis window."""
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.delivery_start_hour = 0
	config.delivery_end_hour = 23
	config.save()

	supplier = frappe.get_all("Supplier", limit=1, pluck="name")[0]
	assign_user(
		{"doctype": "Supplier", "name": supplier, "assign_to": [TEST_USER], "description": "test"}
	)
	frappe.db.commit()

	force_expire_window(TEST_USER)
	with patch.object(DeliveryRestrictions, "is_within_delivery_hours", return_value=True):
		BatchProcessor.process_expired_windows()
	frappe.db.commit()

	entries = frappe.get_all(
		"Assignment Notification Queue",
		filters={"assigned_to": TEST_USER},
		fields=["name", "status"],
	)
	assert len(entries) == 1
	# In a test environment without outgoing email configured, digest send fails gracefully
	assert entries[0].status in ("Sent", "Failed")
	# Window must be cleared after processing
	assert WindowManager.get_window_data(TEST_USER) is None


def test_delivery_hour_restriction_reschedules():
	"""Notifications outside delivery hours are rescheduled — not sent — and receive a
	new window_key pointing to the next delivery slot."""
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.save()

	supplier = frappe.get_all("Supplier", limit=1, pluck="name")[0]
	assign_user(
		{"doctype": "Supplier", "name": supplier, "assign_to": [TEST_USER], "description": "test"}
	)
	frappe.db.commit()

	entry_name = frappe.get_all(
		"Assignment Notification Queue",
		filters={"assigned_to": TEST_USER},
		fields=["name", "window_key"],
	)[0]
	original_window_key = entry_name.window_key

	force_expire_window(TEST_USER)

	# Patch get_next_delivery_time to return a guaranteed-future time so the rescheduled
	# window_key is always different from the original (avoids same-second timestamp clash).
	future_time = add_to_date(now_datetime(), minutes=15)
	with patch.object(
		DeliveryRestrictions, "is_within_delivery_hours", return_value=False
	), patch.object(DeliveryRestrictions, "get_next_delivery_time", return_value=future_time):
		BatchProcessor.process_expired_windows()
	frappe.db.commit()

	updated_status = frappe.db.get_value("Assignment Notification Queue", entry_name.name, "status")
	updated_window_key = frappe.db.get_value(
		"Assignment Notification Queue", entry_name.name, "window_key"
	)
	assert updated_status == "Queued"
	assert updated_window_key != original_window_key

	# A new window must exist in Redis for the next delivery slot
	new_window_data = WindowManager.get_window_data(TEST_USER)
	assert new_window_data is not None
	assert new_window_data["window_key"] == updated_window_key


def test_expired_window_db_fallback():
	"""When Redis TTL has evicted the window data, get_expired_windows falls back to
	the DB (queued entries) and still returns the window for processing."""
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.delivery_start_hour = 0
	config.delivery_end_hour = 23
	config.save()

	supplier = frappe.get_all("Supplier", limit=1, pluck="name")[0]
	assign_user(
		{"doctype": "Supplier", "name": supplier, "assign_to": [TEST_USER], "description": "test"}
	)

	# Simulate Redis TTL expiry — window data gone but DB entry still Queued
	WindowManager.clear_window(TEST_USER)
	assert WindowManager.get_window_data(TEST_USER) is None

	expired = WindowManager.get_expired_windows()
	assert any(w["user"] == TEST_USER for w in expired)


def test_self_assignment_skipped():
	"""An assignment where assigned_by == allocated_to must not create a queue entry."""
	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.save()

	supplier = frappe.get_all("Supplier", limit=1, pluck="name")[0]
	session_user = frappe.session.user
	assign_user(
		{
			"doctype": "Supplier",
			"name": supplier,
			"assign_to": [session_user],
			"assigned_by": session_user,
			"description": "self-assignment",
		}
	)

	queue_entries = frappe.get_all(
		"Assignment Notification Queue", filters={"assigned_to": session_user}
	)
	assert len(queue_entries) == 0


def test_cleanup_removes_old_entries():
	"""cleanup_old_queue_entries deletes Sent/Failed entries older than 30 days
	and leaves recent entries untouched."""
	suppliers = frappe.get_all("Supplier", limit=2, pluck="name")

	old_doc = frappe.get_doc(
		{
			"doctype": "Assignment Notification Queue",
			"assigned_to": TEST_USER,
			"reference_doctype": "Supplier",
			"reference_name": suppliers[0],
			"status": "Sent",
			"notification_sent": 1,
			"processed_at": add_to_date(now_datetime(), days=-31),
		}
	).insert(ignore_permissions=True)

	recent_doc = frappe.get_doc(
		{
			"doctype": "Assignment Notification Queue",
			"assigned_to": TEST_USER,
			"reference_doctype": "Supplier",
			"reference_name": suppliers[1],
			"status": "Sent",
			"notification_sent": 1,
			"processed_at": now_datetime(),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()

	cleanup_old_queue_entries()
	frappe.db.commit()

	assert not frappe.db.exists("Assignment Notification Queue", old_doc.name)
	assert frappe.db.exists("Assignment Notification Queue", recent_doc.name)


def test_digest_routed_through_email_override():
	"""When Notification Log Override is enabled, batched assignment digests use the override path."""
	from communications.communications.email_override_defaults import NOTIFICATION_LOG_OVERRIDE

	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.delivery_start_hour = 0
	config.delivery_end_hour = 23
	config.save()

	frappe.db.set_value("Notification", NOTIFICATION_LOG_OVERRIDE, "enabled", 1)
	invalidate_email_override_cache()
	sendmail_calls = []

	def capture_sendmail(*args, **kwargs):
		sendmail_calls.append(kwargs)

	supplier = frappe.get_all("Supplier", limit=1, pluck="name")[0]
	assign_user(
		{"doctype": "Supplier", "name": supplier, "assign_to": [TEST_USER], "description": "test"}
	)
	frappe.db.commit()

	force_expire_window(TEST_USER)

	with patch.object(DeliveryRestrictions, "is_within_delivery_hours", return_value=True):
		with patch("frappe.sendmail", side_effect=capture_sendmail):
			BatchProcessor.process_expired_windows()
			frappe.db.commit()

			stock_calls = [call for call in sendmail_calls if call.get("template") == "new_notification"]
			override_calls = [call for call in sendmail_calls if call.get("template") != "new_notification"]
			assert not stock_calls
			assert override_calls
			assert any(TEST_USER in (call.get("recipients") or []) for call in override_calls)

	frappe.db.set_value("Notification", NOTIFICATION_LOG_OVERRIDE, "enabled", 0)
	invalidate_email_override_cache()
	frappe.db.commit()


def test_individual_notification_routed_through_email_override():
	"""Priority Task assignments route through Notification Log Override instead of stock sendmail."""
	from communications.communications.email_override_defaults import NOTIFICATION_LOG_OVERRIDE

	config = frappe.get_single("Notification Window Settings")
	config.enabled = 1
	config.bypass_batching_for_priority = 1
	config.priority_doctypes = "Task"
	config.save()

	frappe.db.set_value("Notification", NOTIFICATION_LOG_OVERRIDE, "enabled", 1)
	invalidate_email_override_cache()
	sendmail_calls = []

	def capture_sendmail(*args, **kwargs):
		sendmail_calls.append(kwargs)

	task = frappe.get_doc({"doctype": "Task", "subject": "Test Task Individual"}).insert()

	with patch("frappe.sendmail", side_effect=capture_sendmail):
		assign_user(
			{
				"doctype": "Task",
				"name": task.name,
				"assign_to": [TEST_USER],
				"description": "Test assignment",
			}
		)
		frappe.db.commit()

		stock_calls = [call for call in sendmail_calls if call.get("template") == "new_notification"]
		override_calls = [call for call in sendmail_calls if call.get("template") != "new_notification"]
		assert not stock_calls
		assert override_calls
		assert any("Test assignment" in (call.get("message") or "") for call in override_calls)

	frappe.db.set_value("Notification", NOTIFICATION_LOG_OVERRIDE, "enabled", 0)
	invalidate_email_override_cache()
	frappe.db.commit()
