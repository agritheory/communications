# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

"""Call-site keys for sendmail route tests. Not used at runtime; configure routes in Notification records."""

NOTIFICATION_LOG_ROUTE_KEY = (
	"frappe.desk.doctype.notification_log.notification_log",
	"send_notification_email",
)
WORKFLOW_ACTION_ROUTE_KEY = (
	"frappe.workflow.doctype.workflow_action.workflow_action",
	"send_workflow_action_email",
)
DOCUMENT_FOLLOW_ROUTE_KEY = (
	"frappe.desk.form.document_follow",
	"send_email_alert",
)
