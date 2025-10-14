# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe


class FallbackHandler:
	@staticmethod
	def send_immediate_notification(
		assigned_to: str, reference_doctype: str, reference_name: str, description: str | None = None
	):
		try:
			from communications.notification_scheduler.dispatcher import Dispatcher

			doc = frappe.get_doc(
				{
					"doctype": "Assignment Notification Queue",
					"assigned_to": assigned_to,
					"reference_doctype": reference_doctype,
					"reference_name": reference_name,
					"description": description,
					"bypass_batching": 1,
					"status": "Queued",
				}
			)
			doc.insert(ignore_permissions=True)

			Dispatcher.send_individual_notification(doc.name)

		except Exception as e:
			frappe.log_error(f"Error in fallback notification: {str(e)}", "Fallback Handler")
			FallbackHandler._send_standard_notification(
				assigned_to, reference_doctype, reference_name, description
			)

	@staticmethod
	def _send_standard_notification(
		assigned_to: str, reference_doctype: str, reference_name: str, description: str | None = None
	):
		try:
			from frappe.desk.form.assign_to import add

			add(
				{
					"assign_to": [assigned_to],
					"doctype": reference_doctype,
					"name": reference_name,
					"description": description,
				}
			)
		except Exception as e:
			frappe.log_error(f"Error in standard notification: {str(e)}", "Fallback Handler")
