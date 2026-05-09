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

		rk = (getattr(self, "sendmail_route_key", None) or "").strip()
		if rk:
			from communications.communications.overrides.sendmail_routing import (
				validate_route_key_or_throw,
			)

			validate_route_key_or_throw(rk)

		# self.validate_forbidden_types()
		self.validate_condition()
		self.validate_standard()
		frappe.cache().hdel("notifications", self.document_type)

	def after_insert(self):
		super().after_insert()
		from communications.communications.overrides.sendmail import reconcile_notification_routes

		reconcile_notification_routes()

	def on_update(self):
		super().on_update()
		from communications.communications.overrides.sendmail import reconcile_notification_routes

		reconcile_notification_routes()

	def on_trash(self):
		super().on_trash()
		from communications.communications.overrides.sendmail import reconcile_notification_routes

		reconcile_notification_routes()

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
		except Exception:
			self.log_error("Failed to send Notification")

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
			except Exception:
				self.log_error("Document update failed")

	def get_slack_user_id(self, email):
		slack_token = frappe.db.get_value("Slack Webhook URL", self.slack_webhook_url, "webhook_url")
		slack_client = WebClient(token=slack_token)
		try:
			response = slack_client.users_lookupByEmail(email=email)
			return response["user"]["id"]
		except SlackApiError as e:
			self.log_error(f"Error fetching user ID: {e.response['error']}")
			return None

	def get_teams_user_id(self, email):
		"""Look up Teams user ID by email using Graph API."""
		teams_webhook_doc = frappe.get_doc("Teams Webhook URL", self.teams_webhook_url)
		client = teams_webhook_doc.client()

		response = client.get(
			f"{client.base_url}/users",
			params={"$filter": f"mail eq '{email}' or userPrincipalName eq '{email}'"},
		)

		if response.status_code == 200:
			users = response.json().get("value", [])
			if users:
				return users[0].get("id")

		tenant_domain = frappe.db.get_value("Teams Webhook URL", self.teams_webhook_url, "tenant_domain")
		if tenant_domain:
			external_upn = email.replace("@", "_") + f"#EXT#@{tenant_domain}"
			response = client.get(
				f"{client.base_url}/users",
				params={"$filter": f"userPrincipalName eq '{external_upn}'"},
			)

			if response.status_code == 200:
				users = response.json().get("value", [])
				if users:
					return users[0].get("id")

		self.log_error(f"Teams user not found for email: {email}")
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
				except Exception:
					self.log_error("Failed to send Slack Notification")

	def send_a_teams_dm_msg(self, doc, context):
		"""Send a direct message via Microsoft Teams using Graph API."""
		if frappe.are_emails_muted():
			return

		recipients, cc, bcc = self.get_list_of_recipients(doc, context)

		if not (recipients or cc or bcc):
			return

		recipients += cc + bcc

		teams_webhook_doc = frappe.get_doc("Teams Webhook URL", self.teams_webhook_url)
		client = teams_webhook_doc.client()

		show_link = frappe.db.get_value(
			"Teams Webhook URL", self.teams_webhook_url, "show_document_link"
		)
		doc_url = get_url_to_form(doc.doctype, doc.name)

		message_text = frappe.render_template(self.message, context)

		for recipient in recipients:
			user_id = self.get_teams_user_id(recipient)
			if not user_id:
				continue

			try:
				chat_data = {
					"chatType": "oneOnOne",
					"members": [
						{
							"@odata.type": "#microsoft.graph.aadUserConversationMember",
							"roles": ["owner"],
							"user@odata.bind": f"{client.base_url}/users('{user_id}')",
						}
					],
				}

				chat_response = client.post(f"{client.base_url}/chats", json=chat_data)

				if chat_response.status_code == 201:
					chat_id = chat_response.headers.get("Location", "").split("/")[-1].strip("'")
				elif chat_response.status_code == 409:
					self.log_error(
						f"Existing chat found for {recipient}, but can't retrieve ID with app-only auth"
					)
					continue
				else:
					self.log_error(f"Failed to create chat with {recipient}: {chat_response.status_code}")
					continue

				body_content = f"<p>{message_text}</p>"
				if show_link:
					body_content += f'<p><a href="{doc_url}">Go to the document</a></p>'

				message_data = {"body": {"contentType": "html", "content": body_content}}

				msg_response = client.post(f"{client.base_url}/chats/{chat_id}/messages", json=message_data)

				if msg_response.status_code != 201:
					self.log_error(f"Failed to send Teams message to {recipient}: {msg_response.text}")

			except Exception as e:
				self.log_error(f"Failed to send Teams DM to {recipient}: {str(e)}")
