# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import frappe
from frappe.email.doctype.notification.notification import Notification, get_context
from frappe.utils.jinja import validate_template
from frappe.utils import get_url_to_form

from communications.communications.doctype.teams_webhook_url.teams_webhook_url import (
	TeamsMessagingError,
)

# Error Log title field max 140 chars
TEAMS_DM_LOG_TITLE = "Teams DM send failed"
TEAMS_DM_INIT_LOG_TITLE = "Teams DM client init failed"


def teams_dm_error_body(recipient: str, exc: BaseException) -> str:
	lines = [f"Recipient: {recipient}", ""]
	if isinstance(exc, TeamsMessagingError):
		lines.append(exc.message)
		if exc.details:
			lines.extend(["", "Details:", frappe.as_json(exc.details, indent=2)])
	else:
		lines.extend([str(exc), "", frappe.get_traceback()])
	return "\n".join(lines)


class CommunicationsNotification(Notification):
	# track overrides
	def validate(self):
		if self.channel in ("Email", "Slack", "Slack DM", "Teams DM", "System Notification"):
			validate_template(self.subject)

		validate_template(self.message)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(frappe._("Please specify which date field must be checked"))

		if self.event == "Value Change" and not self.value_changed:
			frappe.throw(frappe._("Please specify which value field must be checked"))

		# self.validate_forbidden_types()
		self.validate_condition()
		self.validate_standard()
		frappe.cache().hdel("notifications", self.document_type)

	def send(self, doc):
		if self.channel not in ("Slack DM", "Teams DM"):
			super().send(doc)
			return

		context = get_context(doc)
		context = {"doc": doc, "alert": self, "comments": None}
		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if self.is_standard:
			self.load_standard_properties(context)
		try:
			if self.channel == "Slack DM":
				self.send_a_slack_dm_msg(doc, context)
			elif self.channel == "Teams DM":
				self.send_a_teams_dm_msg(doc, context)

			if self.channel == "System Notification" or self.send_system_notification:
				self.create_system_notification(doc, context)
		except Exception as e:
			self.log_error("Failed to send Notification", e)

		if self.set_property_after_alert:
			allow_update = True
			if (
				doc.docstatus.is_submitted()
				and not doc.meta.get_field(self.set_property_after_alert).allow_on_submit
			):
				allow_update = False
			try:
				if allow_update and not doc.flags.in_notification_update:
					fieldname = self.set_property_after_alert
					value = self.property_value
					if doc.meta.get_field(fieldname).fieldtype in frappe.model.numeric_fieldtypes:
						value = frappe.utils.cint(value)

					doc.reload()
					doc.set(fieldname, value)
					doc.flags.updater_reference = {
						"doctype": self.doctype,
						"docname": self.name,
						"label": frappe._("via Notification"),
					}
					doc.flags.in_notification_update = True
					doc.save(ignore_permissions=True)
					doc.flags.in_notification_update = False
			except Exception as e:
				self.log_error("Document update failed", e)

	def get_slack_user_id(self, email):
		slack_token = frappe.db.get_value("Slack Webhook URL", self.slack_webhook_url, "webhook_url")
		slack_client = WebClient(token=slack_token)
		try:
			response = slack_client.users_lookupByEmail(email=email)
			return response["user"]["id"]
		except SlackApiError as e:
			self.log_error(f"Error fetching user ID: {e.response['error']}")
			return None

	def send_a_slack_dm_msg(self, doc, context):
		if frappe.are_emails_muted():
			return

		recipients, cc, bcc = self.get_list_of_recipients(doc, context)

		if not (recipients or cc or bcc):
			return

		recipients += cc + bcc
		slack_token, show_link = frappe.db.get_value(
			"Slack Webhook URL", self.slack_webhook_url, ["webhook_url", "show_document_link"]
		)
		slack_client = WebClient(token=slack_token)
		doc_url = get_url_to_form(doc.doctype, doc.name)
		blocks = [
			{
				"type": "section",
				"text": {"type": "mrkdwn", "text": frappe.render_template(self.message, context)},
			},
		]
		if show_link:
			blocks.append(
				{
					"type": "actions",
					"elements": [
						{
							"type": "button",
							"text": {"type": "plain_text", "text": frappe._("Go to the document")},
							"url": doc_url,
						}
					],
				}
			)

		for recipient in recipients:
			slack_user_id = self.get_slack_user_id(recipient)
			if slack_user_id:
				try:
					slack_client.chat_postMessage(channel=slack_user_id, blocks=blocks)
				except Exception as e:
					self.log_error("Failed to send Slack Notification", e)

	def send_a_teams_dm_msg(self, doc, context):
		"""Send a direct message via Microsoft Teams using Bot Framework REST API."""
		recipients, cc, bcc = self.get_list_of_recipients(doc, context)

		if not (recipients or cc or bcc):
			return

		recipients += cc + bcc

		teams_webhook_doc = frappe.get_doc("Teams Webhook URL", self.teams_webhook_url)

		# Check if Bot Framework configuration is complete
		if not (
			teams_webhook_doc.bot_app_id
			and teams_webhook_doc.bot_app_secret
			and teams_webhook_doc.tenant_id
		):
			self.log_error("Teams DM requires Bot App ID, Bot App Secret, and Tenant ID")
			return

		try:
			messaging_client = teams_webhook_doc.get_messaging_client()
		except Exception as e:
			self.log_error(
				title=TEAMS_DM_INIT_LOG_TITLE,
				message=f"{e}\n\n{frappe.get_traceback()}",
			)
			return

		show_link = teams_webhook_doc.show_document_link
		doc_url = get_url_to_form(doc.doctype, doc.name)
		message_text = frappe.render_template(self.message, context)

		# Build message content
		body_content = f"<p>{message_text}</p>"
		if show_link:
			body_content += f'<p><a href="{doc_url}">Go to the document</a></p>'

		for recipient in recipients:
			try:
				messaging_client.send_dm_to_user(email=recipient, message=body_content, content_type="html")
			except Exception as e:
				self.log_error(title=TEAMS_DM_LOG_TITLE, message=teams_dm_error_body(recipient, e))
