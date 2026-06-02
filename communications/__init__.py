# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
#
# Email Override patches: see communications/docs/sendmail-routes.md

__version__ = "15.6.0"

import frappe

from communications.email_overrides import try_email_override


def patch_sendmail_recursion_guard() -> None:
	"""Allow CommunicationsNotification.send_an_email to call frappe.sendmail without re-intercepting."""
	original = frappe.sendmail

	def guarded_sendmail(*args, **kwargs):
		if getattr(frappe.local, "in_email_override", False):
			return original(*args, **kwargs)
		return original(*args, **kwargs)

	frappe.sendmail = guarded_sendmail


def patch_send_notification_email() -> None:
	from frappe.desk.doctype.notification_log import notification_log as notification_log_module
	from frappe.utils import get_url_to_form, strip_html

	original = notification_log_module.send_notification_email

	def send_notification_email(doc):
		if doc.type == "Energy Point" and doc.email_content is None:
			return

		log_type = doc.type or ""
		if log_type in {"Mention", "Assignment", "Share", "Energy Point", "Alert"}:
			user = frappe.db.get_value("User", doc.for_user, fieldname=["email", "language"], as_dict=True)
			if not user:
				return

			from frappe.desk.doctype.notification_log.notification_log import get_email_header

			header = get_email_header(doc, user.language)
			email_subject = strip_html(doc.subject)
			args = {
				"body_content": doc.subject,
				"description": doc.email_content,
			}
			if doc.link:
				args["doc_link"] = doc.link
			else:
				args["document_type"] = doc.document_type
				args["document_name"] = doc.document_name
				args["doc_link"] = get_url_to_form(doc.document_type, doc.document_name)

			kwargs = {
				"recipients": user.email,
				"subject": email_subject,
				"template": "new_notification",
				"args": args,
				"header": [header, "orange"],
				"now": frappe.flags.in_test,
				"notification_log_type": log_type,
				"notification_log": {
					"type": doc.type,
					"subject": doc.subject,
					"email_content": doc.email_content,
					"from_user": doc.from_user,
					"for_user": doc.for_user,
					"document_type": doc.document_type,
					"document_name": doc.document_name,
				},
			}

			if doc.document_type and doc.document_name:
				context_doc = frappe.get_doc(doc.document_type, doc.document_name)
				if try_email_override("Mention, Assignment, Share, Energy Point, Alert", context_doc, kwargs):
					return

		return original(doc)

	notification_log_module.send_notification_email = send_notification_email


def patch_document_follow() -> None:
	from frappe.desk.form import document_follow as document_follow_module
	from frappe import _

	original = document_follow_module.send_email_alert

	def send_email_alert(receiver, docinfo, timeline):
		if not receiver:
			return

		kwargs = {
			"subject": _("Document Follow Notification"),
			"recipients": [receiver],
			"template": "document_follow",
			"args": {
				"docinfo": docinfo,
				"timeline": timeline,
			},
		}

		from communications.email_overrides import resolve_override_reference

		ref_doctype, ref_name = resolve_override_reference(kwargs)
		if ref_doctype and ref_name:
			context_doc = frappe.get_doc(ref_doctype, ref_name)
			if try_email_override("Document Follow", context_doc, kwargs):
				return

		return original(receiver, docinfo, timeline)

	document_follow_module.send_email_alert = send_email_alert


def patch_workflow_action() -> None:
	from frappe.workflow.doctype.workflow_action import workflow_action as workflow_action_module

	original = workflow_action_module.send_workflow_action_email

	def send_workflow_action_email(doc, transitions):
		users_data = workflow_action_module.get_users_next_action_data(transitions, doc)
		common_args = workflow_action_module.get_common_email_args(doc)
		message = common_args.pop("message", None)

		for data in users_data.values():
			email_args = {
				"recipients": [data.get("email")],
				"args": {
					"actions": list(workflow_action_module.deduplicate_actions(data.get("possible_actions"))),
					"message": message,
				},
				"reference_name": doc.name,
				"reference_doctype": doc.doctype,
			}
			email_args.update(common_args)

			if try_email_override("Workflow Action", doc, email_args):
				continue

			try:
				frappe.sendmail(**email_args)
			except frappe.OutgoingEmailError:
				frappe.log_error("Failed to send workflow action email")
				return

	workflow_action_module.send_workflow_action_email = send_workflow_action_email


def patch_event_digest() -> None:
	from frappe.desk.doctype.event import event as event_module
	from frappe.utils.user import get_enabled_system_users

	def send_event_digest():
		today = event_module.getdate()
		users = [
			user
			for user in get_enabled_system_users()
			if event_module.is_email_notifications_enabled_for_type(user.name, "Event Reminders")
		]

		for user in users:
			events = event_module.get_events(today, today, user.name, for_reminder=True)
			if not events:
				continue

			frappe.set_user_lang(user.name, user.language)

			for event_row in events:
				event_row.starts_on = event_module.format_datetime(event_row.starts_on, "hh:mm a")
				if event_row.all_day:
					event_row.starts_on = "All Day"

			kwargs = {
				"recipients": user.email,
				"subject": frappe._("Upcoming Events for Today"),
				"template": "upcoming_events",
				"args": {"events": events},
				"header": [frappe._("Events in Today's Calendar"), "blue"],
			}

			context_doc = frappe.get_doc("User", user.name)
			if try_email_override("Event Digest", context_doc, kwargs):
				continue

			frappe.sendmail(**kwargs)

	event_module.send_event_digest = send_event_digest


def patch_evaluate_alert() -> None:
	from frappe.email.doctype.notification import notification as notification_module

	original = notification_module.evaluate_alert

	def evaluate_alert(doc, alert, event):
		alert_name = alert if isinstance(alert, str) else alert.name
		if frappe.db.get_value("Notification", alert_name, "email_override"):
			return
		return original(doc, alert, event)

	notification_module.evaluate_alert = evaluate_alert


patch_sendmail_recursion_guard()
patch_send_notification_email()
patch_document_follow()
patch_workflow_action()
patch_event_digest()
patch_evaluate_alert()
