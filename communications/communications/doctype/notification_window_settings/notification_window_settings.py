# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import pytz
import frappe
from frappe import _
from frappe.model.document import Document


class NotificationWindowSettings(Document):
	def validate(self):
		if self.delivery_start_hour < 0 or self.delivery_start_hour > 23:
			frappe.throw(_("Start hour must be between 0 and 23"))

		if self.delivery_end_hour < 0 or self.delivery_end_hour > 23:
			frappe.throw(_("End hour must be between 0 and 23"))

		if self.delivery_start_hour == self.delivery_end_hour:
			frappe.throw(_("Delivery start and end hours cannot be the same"))

		if self.collection_window_minutes < 1:
			frappe.throw(_("Collection window must be at least 1 minute"))

		if self.max_digest_size < 1:
			frappe.throw(_("Max digest size must be at least 1"))

		if self.time_zone:
			try:
				pytz.timezone(self.time_zone)
			except pytz.exceptions.UnknownTimeZoneError:
				frappe.throw(_("Invalid timezone: {0}").format(self.time_zone))

	@staticmethod
	def get_config():
		config = frappe.cache().get_value("notification_window_settings")

		if not config:
			try:
				doc = frappe.get_single("Notification Window Settings")
				config = frappe._dict(
					{
						"enabled": doc.enabled,
						"collection_window_minutes": doc.collection_window_minutes
						if doc.collection_window_minutes is not None
						else 15,
						"max_digest_size": doc.max_digest_size if doc.max_digest_size is not None else 50,
						"delivery_start_hour": doc.delivery_start_hour if doc.delivery_start_hour is not None else 8,
						"delivery_end_hour": doc.delivery_end_hour if doc.delivery_end_hour is not None else 20,
						"time_zone": doc.time_zone or "UTC",
						"bypass_batching_for_priority": doc.bypass_batching_for_priority,
						"priority_doctypes": [
							dt.strip() for dt in (doc.priority_doctypes or "").split(",") if dt.strip()
						],
						"batch_template": doc.batch_template,
						"individual_template": doc.individual_template,
					}
				)
				frappe.cache().set_value("notification_window_settings", config, expires_in_sec=300)
			except Exception:
				config = frappe._dict(
					{
						"enabled": False,
						"collection_window_minutes": 15,
						"max_digest_size": 50,
						"delivery_start_hour": 8,
						"delivery_end_hour": 20,
						"time_zone": "UTC",
						"bypass_batching_for_priority": False,
						"priority_doctypes": [],
						"batch_template": None,
						"individual_template": None,
					}
				)
		return config

	def on_update(self):
		frappe.cache().delete_value("notification_window_settings")
