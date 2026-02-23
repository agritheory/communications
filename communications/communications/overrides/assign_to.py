# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)


def send_notification_for_doc(notification_name, doc_type, doc_name):
	notification = frappe.get_doc("Notification", notification_name)
	doc = frappe.get_doc(doc_type, doc_name)
	notification.send(doc)


def custom_notify_assignment(
	assigned_by, allocated_to, doc_type, doc_name, action="CLOSE", description=None
):
	"""
	Monkey patch for notify_assignment to use Notification DocType if configured.
	"""
	if not (assigned_by and allocated_to and doc_type and doc_name):
		return

	assigned_user = frappe.db.get_value("User", allocated_to, ["language", "enabled"], as_dict=True)

	# return if self assigned or user disabled
	if assigned_by == allocated_to or not assigned_user.enabled:
		return

	# Check if a Notification is configured for ToDo
	notification_name = frappe.get_all(
		"Notification", {"document_type": "ToDo", "enabled": 1}, order_by="modified desc", pluck="name"
	)
	if notification_name:
		notification_name = notification_name[0]
		try:
			frappe.enqueue(
				"communications.communications.overrides.assign_to.send_notification_for_doc",
				notification_name=notification_name,
				doc_type=doc_type,
				doc_name=doc_name,
			)
			return
		except Exception as e:
			frappe.log_error(
				f"Failed to send Notification DocType for assignment: {str(e)}", "custom_notify_assignment"
			)

	# Search for email address in description -- i.e. assignee
	user_name = frappe.get_cached_value("User", frappe.session.user, "full_name")
	title = get_title(doc_type, doc_name)
	description_html = f"<div>{description}</div>" if description else None

	if action == "CLOSE":
		subject = _(
			"Your assignment on {0} {1} has been removed by {2}", lang=assigned_user.language
		).format(frappe.bold(_(doc_type)), get_title_html(title), frappe.bold(user_name))
	else:
		user_name = frappe.bold(user_name)
		document_type = frappe.bold(_(doc_type, lang=assigned_user.language))
		title = get_title_html(title)
		subject = _("{0} assigned a new task {1} {2} to you", lang=assigned_user.language).format(
			user_name, document_type, title
		)

	notification_doc = {
		"type": "Assignment",
		"document_type": doc_type,
		"subject": subject,
		"document_name": doc_name,
		"from_user": frappe.session.user,
		"email_content": description_html,
	}

	enqueue_create_notification(allocated_to, notification_doc)
