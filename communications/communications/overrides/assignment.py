# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.utils.data import strip_html
from frappe.desk.form.document_follow import follow_document
from frappe.desk.form.assign_to import get, notify_assignment, format_message_for_assign_to
from communications.notification_scheduler.window_manager import WindowManager
from communications.notification_scheduler.utils import FallbackHandler
from communications.communications.doctype.notification_window_settings.notification_window_settings import (
	NotificationWindowSettings,
)


@frappe.whitelist()
def add(args=None, *, ignore_permissions=False):
	"""add in someone's to do list
	args = {
	                "assign_to": [],
	                "doctype": ,
	                "name": ,
	                "description": ,
	                "assignment_rule":
	}

	"""
	if not args:
		args = frappe.local.form_dict

	users_with_duplicate_todo = []
	shared_with_users = []

	for assign_to in frappe.parse_json(args.get("assign_to")):
		filters = {
			"reference_type": args["doctype"],
			"reference_name": args["name"],
			"status": "Open",
			"allocated_to": assign_to,
		}
		if not ignore_permissions:
			frappe.get_doc(args["doctype"], args["name"]).check_permission()

		if frappe.get_all("ToDo", filters=filters):
			users_with_duplicate_todo.append(assign_to)
		else:
			from frappe.utils import nowdate

			description = args.get("description") or ""
			has_content = strip_html(description) or "<img" in description
			if not has_content:
				args["description"] = _("Assignment for {0} {1}").format(args["doctype"], args["name"])

			d = frappe.get_doc(
				{
					"doctype": "ToDo",
					"allocated_to": assign_to,
					"reference_type": args["doctype"],
					"reference_name": str(args["name"]),
					"description": args.get("description"),
					"priority": args.get("priority", "Medium"),
					"status": "Open",
					"date": args.get("date", nowdate()),
					"assigned_by": args.get("assigned_by", frappe.session.user),
					"assignment_rule": args.get("assignment_rule"),
				}
			).insert(ignore_permissions=True)

			# set assigned_to if field exists
			if frappe.get_meta(args["doctype"]).get_field("assigned_to"):
				frappe.db.set_value(args["doctype"], args["name"], "assigned_to", assign_to)

			doc = frappe.get_doc(args["doctype"], args["name"])

			# if assignee does not have permissions, share or inform
			if not frappe.has_permission(doc=doc, user=assign_to):
				if frappe.get_system_settings("disable_document_sharing"):
					msg = _("User {0} is not permitted to access this document.").format(frappe.bold(assign_to))
					msg += "<br>" + _(
						"As document sharing is disabled, please give them the required permissions before assigning."
					)
					frappe.throw(msg, title=_("Missing Permission"))
				else:
					frappe.share.add(doc.doctype, doc.name, assign_to)
					shared_with_users.append(assign_to)

			# make this document followed by assigned user
			if frappe.get_cached_value("User", assign_to, "follow_assigned_documents"):
				follow_document(args["doctype"], args["name"], assign_to)

			# ============ CUSTOM NOTIFICATION LOGIC ============
			config = NotificationWindowSettings.get_config()
			if config.enabled:
				try:
					queue_assignment_notification(
						assigned_by=d.assigned_by,
						allocated_to=d.allocated_to,
						doc_type=d.reference_type,
						doc_name=d.reference_name,
						description=args.get("description"),
						config=config,
					)
				except Exception as e:
					frappe.log_error(
						f"Error queueing notification for {assign_to}: {str(e)}", "Assignment Override"
					)
					notify_assignment(
						d.assigned_by,
						d.allocated_to,
						d.reference_type,
						d.reference_name,
						action="ASSIGN",
						description=args.get("description"),
					)
			else:
				notify_assignment(
					d.assigned_by,
					d.allocated_to,
					d.reference_type,
					d.reference_name,
					action="ASSIGN",
					description=args.get("description"),
				)
			# ============ END CUSTOM LOGIC ============

	if shared_with_users:
		user_list = format_message_for_assign_to(shared_with_users)
		frappe.msgprint(
			_("Shared with the following Users with Read access:{0}").format(user_list),
			alert=True,
		)

	if users_with_duplicate_todo:
		user_list = format_message_for_assign_to(users_with_duplicate_todo)
		frappe.msgprint(
			_("Already in the following Users ToDo list:{0}").format(user_list),
			alert=True,
		)

	return get(args)


def queue_assignment_notification(
	assigned_by, allocated_to, doc_type, doc_name, description, config
):
	try:
		if not (assigned_by and allocated_to and doc_type and doc_name):
			return

		assigned_user = frappe.db.get_value("User", allocated_to, ["language", "enabled"], as_dict=True)

		# return if self assigned or user disabled
		if assigned_by == allocated_to or not assigned_user.enabled:
			return

		bypass = False
		if config.bypass_batching_for_priority and doc_type in config.priority_doctypes:
			bypass = True

		queue_doc = frappe.get_doc(
			{
				"doctype": "Assignment Notification Queue",
				"assigned_to": allocated_to,
				"reference_doctype": doc_type,
				"reference_name": doc_name,
				"description": description,
				"assigned_by": assigned_by,
				"bypass_batching": bypass,
				"status": "Queued",
			}
		)
		queue_doc.insert(ignore_permissions=True)

		if bypass:
			from communications.notification_scheduler.dispatcher import Dispatcher

			Dispatcher.send_individual_notification(queue_doc.name)
		else:
			WindowManager.increment_notification_count(allocated_to)
	except Exception as e:
		frappe.log_error(
			f"Error queuing notification for {allocated_to}: {str(e)}", "Assignment Override"
		)
		FallbackHandler.send_immediate_notification(allocated_to, doc_type, doc_name, description)
