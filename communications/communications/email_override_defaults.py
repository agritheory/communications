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

DEFAULT_EMAIL_OVERRIDE_NOTIFICATIONS = (
	{
		"name": "Document Follow Override",
		"event": "Document Follow",
		"email_override": "Document Follow",
		"subject": "Document Follow",
		"message": DOCUMENT_FOLLOW_MESSAGE,
	},
	{
		"name": "Workflow Action Override",
		"event": "Workflow Action",
		"email_override": "Workflow Action",
		"subject": "Workflow Action",
		"message": WORKFLOW_ACTION_MESSAGE,
	},
	{
		"name": "Event Digest Override",
		"event": "Event Digest",
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
