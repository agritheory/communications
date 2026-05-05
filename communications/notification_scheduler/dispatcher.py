# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_url, now_datetime, get_url_to_form, strip_html
from frappe.desk.doctype.notification_log.notification_log import (
	get_title,
	get_title_html,
)
from communications.communications.doctype.notification_window_settings.notification_window_settings import (
	NotificationWindowSettings,
)


class Dispatcher:
	@staticmethod
	def send_digest(user: str, digest_content: dict, notifications: list[dict]) -> bool:
		try:
			user_email = frappe.db.get_value("User", user, "email")
			if not user_email:
				frappe.log_error(f"No email found for user {user}", "Dispatcher")
				return False

			frappe.sendmail(
				recipients=[user_email],
				subject=digest_content["subject"],
				message=digest_content["html"],
				reference_doctype="Assignment Notification Queue",
				reference_name=notifications[0]["name"] if notifications else None,
				now=frappe.flags.in_test,
			)
			return True

		except Exception as e:
			frappe.log_error(f"Error sending digest to {user}: {str(e)}", "Dispatcher")
			return False

	@staticmethod
	def send_individual_notification(notification_name: str) -> bool:
		try:
			doc = frappe.get_doc("Assignment Notification Queue", notification_name)
			frappe.db.set_value("Assignment Notification Queue", notification_name, "status", "Processing")

			user_email = frappe.db.get_value("User", doc.assigned_to, "email")
			if not user_email:
				frappe.db.set_value("Assignment Notification Queue", notification_name, "status", "Failed")
				return False

			config = NotificationWindowSettings.get_config()
			template = config.individual_template

			if template:
				email_template = frappe.get_doc("Email Template", template)
				context = {
					"doc": doc,
					"doc_url": get_url(f"/app/{frappe.scrub(doc.reference_doctype)}/{doc.reference_name}"),
				}
				html = frappe.render_template(email_template.response_, context)
				subject = email_template.subject or f"New assignment: {doc.reference_name}"
				frappe.sendmail(
					recipients=[user_email],
					subject=subject,
					message=html,
					reference_doctype=doc.reference_doctype,
					reference_name=doc.reference_name,
					now=frappe.flags.in_test,
				)
			else:
				assigned_user = frappe.db.get_value(
					"User", doc.assigned_to, ["language", "enabled", "email"], as_dict=True
				)
				user_name = frappe.bold(frappe.get_cached_value("User", frappe.session.user, "full_name"))
				html = f"<div>{doc.description}</div>" if doc.description else None
				document_type = frappe.bold(_(doc.reference_doctype, lang=assigned_user.language))
				title = get_title_html(get_title(doc.reference_doctype, doc.reference_name))
				subject = _("{0} assigned a new task {1} {2} to you", lang=assigned_user.language).format(
					user_name, document_type, title
				)
				args = {
					"body_content": subject,
					"description": html,
					"document_type": doc.reference_doctype,
					"document_name": doc.reference_name,
					"doc_link": get_url_to_form(doc.reference_doctype, doc.reference_name),
				}
				header = _("Assignment Update on {0}", lang=assigned_user.language).format(doc.reference_name)
				frappe.sendmail(
					recipients=assigned_user.email,
					subject=strip_html(subject),
					template="new_notification",
					args=args,
					header=[header, "orange"],
					now=frappe.flags.in_test,
				)
			frappe.db.set_value(
				"Assignment Notification Queue",
				notification_name,
				{"status": "Sent", "processed_at": now_datetime(), "notification_sent": 1},
			)
			return True

		except Exception as e:
			frappe.log_error(
				f"Error sending individual notification {notification_name}: {str(e)}", "Dispatcher"
			)
			frappe.db.set_value(
				"Assignment Notification Queue",
				notification_name,
				{"status": "Failed", "processed_at": now_datetime()},
			)
			return False
