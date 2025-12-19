# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import frappe
from frappe.email.doctype.notification.notification import Notification, get_context
from frappe.utils.jinja import validate_template
from frappe.utils import get_url_to_form


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

	def get_teams_conversation_reference(self, email):
		"""Get stored Teams conversation reference for user."""
		cache_key = f"teams_conversation_ref:{email}"
		conv_ref_json = frappe.cache().get_value(cache_key)

		if not conv_ref_json:
			return None

		try:
			return json.loads(conv_ref_json)
		except Exception as e:
			return None

	def send_a_slack_dm_msg(self, doc, context):
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
		"""Send a direct message via Microsoft Teams."""
		import requests

		recipients, cc, bcc = self.get_list_of_recipients(doc, context)

		if not (recipients or cc or bcc):
			return

		recipients += cc + bcc

		teams_webhook_doc = frappe.get_doc("Teams Webhook URL", self.teams_webhook_url)

		if not teams_webhook_doc.use_bot_framework:
			self.log_error("Teams DM requires bot credentials to be configured")
			return

		bot_creds = teams_webhook_doc.get_bot_credentials()
		show_link = teams_webhook_doc.show_document_link
		doc_url = get_url_to_form(doc.doctype, doc.name)
		message_text = frappe.render_template(self.message, context)

		# Build message content
		body_content = f"<p>{message_text}</p>"
		if show_link:
			body_content += f'<p><a href="{doc_url}">Go to the document</a></p>'

		# Get bot token (cached)
		token = self._get_teams_bot_token(bot_creds)
		if not token:
			self.log_error("Failed to get Teams bot token")
			return

		for recipient in recipients:
			conv_ref = self.get_teams_conversation_reference(recipient)
			if not conv_ref:
				self.log_error(
					f"No Teams conversation reference for {recipient}. User must message the bot first."
				)
				continue

			try:
				# Build activity for Bot Connector API
				activity = {
					"type": "message",
					"from": {"id": bot_creds["app_id"], "name": conv_ref.get("bot", {}).get("name", "Bot")},
					"conversation": {"id": conv_ref["conversation"]["id"]},
					"recipient": conv_ref["user"],
					"text": body_content,
					"textFormat": "html",
				}

				# Send to Bot Connector API
				service_url = conv_ref["serviceUrl"]
				conversation_id = conv_ref["conversation"]["id"]
				endpoint = f"{service_url}/v3/conversations/{conversation_id}/activities"

				headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

				response = requests.post(endpoint, headers=headers, json=activity)

				if response.status_code not in (200, 201):
					self.log_error(f"Failed to send Teams message to {recipient}: {response.text}")

			except Exception as e:
				self.log_error(f"Failed to send Teams DM to {recipient}", e)

	def _get_teams_bot_token(self, bot_creds):
		"""Get Bot Framework access token (with caching)."""
		import requests

		# Check cache
		cache_key = f"teams_bot_token:{bot_creds['app_id']}"
		cached_token = frappe.cache().get_value(cache_key)
		if cached_token:
			return cached_token

		# Get new token
		token_url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
		data = {
			"grant_type": "client_credentials",
			"client_id": bot_creds["app_id"],
			"client_secret": bot_creds["app_password"],
			"scope": "https://api.botframework.com/.default",
		}

		try:
			response = requests.post(token_url, data=data)
			response.raise_for_status()

			result = response.json()
			token = result["access_token"]

			# Cache for 55 minutes (tokens expire in 1 hour)
			frappe.cache().set_value(cache_key, token, expires_in_sec=3300)

			return token
		except Exception as e:
			frappe.log_error("Failed to get Teams bot token", e)
			return None
