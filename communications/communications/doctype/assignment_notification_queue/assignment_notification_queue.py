# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from communications.notification_scheduler.window_manager import WindowManager


class AssignmentNotificationQueue(Document):
	def before_insert(self):
		if not self.window_key:
			self.window_key = WindowManager.generate_window_key(self.assigned_to)

	def validate(self):
		config = frappe.get_single("Notification Window Settings").get_config()
		if config.bypass_batching_for_priority and self.reference_doctype in config.priority_doctypes:
			self.bypass_batching = 1
