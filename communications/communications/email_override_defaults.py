# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

"""Default Notification rows for Email Override (installed disabled; enable in Desk)."""

import frappe

DOCUMENT_FOLLOW_MESSAGE = """\
{{ sendmail_subject }}

{% for followed in sendmail_docinfo %}
**{{ followed.reference_doctype }}:** {{ followed.reference_docname }}
{% for entry in sendmail_timeline %}
{% if entry.doctype == followed.reference_doctype and entry.doc_name == followed.reference_docname %}
{% if entry.type == "comment" %}
• {{ entry.data.time }} — {{ entry.data.comment | striptags }} ({{ entry.data.by | striptags }})
{% elif entry.type == "field changed" %}
• {{ entry.data.time }} — {{ entry.data.field }}: {{ entry.data.from }} → {{ entry.data.to }} ({{ entry.by }})
{% elif entry.type == "row changed" %}
• {{ entry.data.time }} — {{ entry.data.table_field }} row {{ entry.data.row }}: {{ entry.data.field }} ({{ entry.by }})
{% elif entry.type == "row added" %}
• {{ entry.data.time }} — row added to {{ entry.data.to }} ({{ entry.by }})
{% endif %}
{% endif %}
{% endfor %}

{% endfor %}"""

WORKFLOW_ACTION_MESSAGE = """\
{% if sendmail_workflow_message %}
{{ sendmail_workflow_message | striptags }}
{% else %}
{{ sendmail_subject }}
{% endif %}

{% for action in sendmail_workflow_actions %}
• <{{ action.action_link }}|{{ action.action_name }}>
{% endfor %}"""

EVENT_DIGEST_MESSAGE = """\
{{ sendmail_subject }}

{% for event in sendmail_events %}
• *{{ event.starts_on }}* — {{ event.subject }}
{% if event.description %}{{ event.description | striptags }}{% endif %}
{% endfor %}"""

DESK_NOTIFICATION_LOG_MESSAGE = """\
{% if sendmail_notification_log_type == "Assignment" %}
{{ sendmail_subject }}
{% elif sendmail_notification_log_type == "Mention" %}
{{ sendmail_from_user }} mentioned you: {{ sendmail_message | striptags }}
{% elif sendmail_notification_log_type == "Share" %}
{{ sendmail_subject }}
{% else %}
{{ sendmail_subject }}
{% endif %}"""

DEFAULT_EMAIL_OVERRIDE_NOTIFICATIONS = (
	{
		"name": "Desk Notification Log Override",
		"email_override": "Mention, Assignment, Share, Energy Point, Alert",
		"subject": "Desk Notification",
		"message": DESK_NOTIFICATION_LOG_MESSAGE,
	},
	{
		"name": "Document Follow Override",
		"email_override": "Document Follow",
		"subject": "Document Follow",
		"message": DOCUMENT_FOLLOW_MESSAGE,
	},
	{
		"name": "Workflow Action Override",
		"email_override": "Workflow Action",
		"subject": "Workflow Action",
		"message": WORKFLOW_ACTION_MESSAGE,
	},
	{
		"name": "Event Digest Override",
		"email_override": "Event Digest",
		"subject": "Event Digest",
		"message": EVENT_DIGEST_MESSAGE,
	},
)


def create_default_email_override_notifications():
	"""Create starter Email Override Notification rows (disabled until configured)."""
	if not frappe.db.has_column("Notification", "email_override"):
		return

	for notification_data in DEFAULT_EMAIL_OVERRIDE_NOTIFICATIONS:
		if frappe.db.exists("Notification", notification_data["name"]):
			continue

		frappe.get_doc(
			{
				"doctype": "Notification",
				"enabled": 0,
				"is_standard": 0,
				"channel": "Email",
				"message_type": "Markdown",
				"document_type": "",
				"days_in_advance": 0,
				"send_system_notification": 0,
				"send_to_all_assignees": 0,
				"attach_print": 0,
				**notification_data,
			}
		).insert(ignore_permissions=True)


SLACK_DM_OVERRIDE_NAMES = (
	"Desk Notification Log Override",
	"Document Follow Override",
)


def get_default_slack_webhook_url() -> str | None:
	"""Return the first Slack Webhook URL record name, if any."""
	rows = frappe.get_all("Slack Webhook URL", pluck="name", limit=1, order_by="modified desc")
	return rows[0] if rows else None


def configure_slack_dm_override_notifications(slack_webhook_url: str | None = None) -> None:
	"""Enable Slack DM routing for default email-override notifications when a webhook exists."""
	if not frappe.db.has_column("Notification", "email_override"):
		return

	slack_webhook_url = slack_webhook_url or get_default_slack_webhook_url()
	if not slack_webhook_url:
		return

	create_default_email_override_notifications()

	for name in SLACK_DM_OVERRIDE_NAMES:
		if not frappe.db.exists("Notification", name):
			continue

		doc = frappe.get_doc("Notification", name)
		doc.channel = "Slack DM"
		doc.slack_webhook_url = slack_webhook_url
		doc.enabled = 1
		doc.send_system_notification = 1
		doc.save(ignore_permissions=True)

	from communications.communications.email_overrides import invalidate_email_override_cache

	invalidate_email_override_cache()
