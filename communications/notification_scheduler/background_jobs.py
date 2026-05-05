# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_to_date, now_datetime

from communications.notification_scheduler.batch_processor import BatchProcessor
from communications.communications.doctype.notification_window_settings.notification_window_settings import (
	NotificationWindowSettings,
)


def process_notification_windows():
	try:
		config = NotificationWindowSettings.get_config()
		if not config.enabled:
			return

		BatchProcessor.process_expired_windows()

	except Exception as e:
		frappe.log_error(f"Error in scheduled task: {str(e)}", "Scheduled Tasks")


def cleanup_old_queue_entries():
	try:
		cutoff_date = add_to_date(now_datetime(), days=-30)
		frappe.db.delete(
			"Assignment Notification Queue",
			{
				"status": ["in", ["Sent", "Failed"]],
				"processed_at": ["<", cutoff_date],
			},
		)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(f"Error cleaning up queue: {str(e)}", "Scheduled Tasks")
