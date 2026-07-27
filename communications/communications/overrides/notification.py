# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.email.doctype.notification.notification import (
	Notification,
	get_context,
	get_reference_doctype,
	get_reference_name,
)
from frappe.utils import get_url_to_form
from frappe.utils.jinja import validate_template

from communications.communications.doctype.teams_webhook_url.teams_webhook_url import (
	TeamsMessagingError,
)
from communications.communications.email_overrides import normalize_route_recipients
from communications.communications.slack_markdown import convert_html_to_slack_mrkdwn

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


def get_email_override_locals():
	recipients = getattr(frappe.local, "email_override_recipients", None)
	subject = getattr(frappe.local, "email_override_subject", None)
	message = getattr(frappe.local, "email_override_message", None)
	attachments = getattr(frappe.local, "email_override_attachments", None)
	extra = getattr(frappe.local, "email_override_extra", None) or {}
	return recipients, subject, message, attachments, extra


def build_notification_template_context(doc, alert=None, comments=None):
	context = get_context(doc)
	context["alert"] = alert
	if comments is not None:
		context["comments"] = comments
	elif doc.get("_comments"):
		context["comments"] = json.loads(doc.get("_comments"))
	else:
		context.setdefault("comments", None)
	return context


def render_notification_template(template, context):
	if not template:
		return ""
	return frappe.render_template(template, context, is_path=False)


def apply_email_override_context(
	context,
	route_subject=None,
	route_message=None,
	route_extra=None,
):
	if route_subject:
		context["sendmail_subject"] = route_subject
	if route_message:
		context["sendmail_message"] = route_message
	if not route_extra:
		return
	if route_extra.get("docinfo") is not None:
		context["sendmail_docinfo"] = route_extra.get("docinfo")
	if route_extra.get("timeline") is not None:
		context["sendmail_timeline"] = route_extra.get("timeline")
	if route_extra.get("workflow_actions") is not None:
		context["sendmail_workflow_actions"] = route_extra.get("workflow_actions")
	if route_extra.get("workflow_message"):
		context["sendmail_workflow_message"] = route_extra.get("workflow_message")
	if route_extra.get("events") is not None:
		context["sendmail_events"] = route_extra.get("events")
	if route_extra.get("notification_log_type"):
		context["sendmail_notification_log_type"] = route_extra.get("notification_log_type")
	if route_extra.get("notification_log"):
		log = frappe._dict(route_extra.get("notification_log"))
		context["sendmail_notification_log"] = log
		if log.get("from_user"):
			context["sendmail_from_user"] = frappe.utils.get_fullname(log.from_user)


def send_slack_or_teams_dm_notification(
	notification_name: str,
	doc_type: str,
	doc_name: str,
	route_recipients: list | None = None,
	route_subject: str | None = None,
	route_message: str | None = None,
	route_extra: dict | None = None,
) -> None:
	"""Background job: load Notification + document and send Slack DM or Teams DM."""
	if frappe.flags.in_migrate:
		return

	alert = frappe.get_doc("Notification", notification_name)
	doc = frappe.get_doc(doc_type, doc_name)
	context = build_notification_template_context(doc, alert=alert)

	if alert.is_standard:
		alert.load_standard_properties(context)

	apply_email_override_context(context, route_subject, route_message, route_extra)

	if route_recipients:
		frappe.local.email_override_recipients = normalize_route_recipients(list(route_recipients))
	if route_subject is not None:
		frappe.local.email_override_subject = route_subject
	if route_message is not None:
		frappe.local.email_override_message = route_message
	if route_extra:
		frappe.local.email_override_extra = route_extra
	try:
		if alert.channel == "Slack DM":
			alert.send_a_slack_dm_msg(doc, context)
		elif alert.channel == "Teams DM":
			alert.send_a_teams_dm_msg(doc, context)
	except Exception as e:
		alert.log_error("Failed to send Notification", e)
	finally:
		frappe.local.email_override_recipients = None
		frappe.local.email_override_extra = None


class CommunicationsNotification(Notification):
	# track overrides
	def validate(self):
		if self.channel in ("Email", "Slack", "Slack DM", "Teams DM", "System Notification"):
			validate_template(self.subject)

		validate_template(self.message)

		if self.get("email_override"):
			if self.subject and "{{" in self.subject:
				frappe.msgprint(
					frappe._(
						"Email Override notifications use Subject as the document title when a "
						"Notification record is assigned. Use plain text in Subject and put Jinja "
						"templates in Message (for example <code>{{ sendmail_subject }}</code>)."
					),
					indicator="orange",
					title=frappe._("Subject is not rendered on assignment"),
				)
			if self.document_type:
				frappe.cache().hdel("notifications", self.document_type)
			return

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(frappe._("Please specify which date field must be checked"))

		if self.event == "Value Change" and not self.value_changed:
			frappe.throw(frappe._("Please specify which value field must be checked"))

		# self.validate_forbidden_types()
		self.validate_condition()
		self.validate_standard()
		frappe.cache().hdel("notifications", self.document_type)

	def send_an_email(self, doc, context):
		"""Honor recipients/subject/body lifted from an intercepted frappe.sendmail call."""
		from email.utils import formataddr

		from frappe.core.doctype.communication.email import _make as make_communication

		(
			route_recipients,
			route_subject,
			route_message,
			route_attachments,
			route_extra,
		) = get_email_override_locals()
		apply_email_override_context(context, route_subject, route_message, route_extra)

		subject = self.subject
		if route_recipients and route_subject:
			subject = route_subject
		if "{" in (subject or ""):
			subject = render_notification_template(subject, context)

		if route_attachments:
			attachments = route_attachments
		else:
			attachments = self.get_attachment(doc)
		if route_recipients:
			recipients = list(route_recipients)
			cc, bcc = [], []
		else:
			recipients, cc, bcc = self.get_list_of_recipients(doc, context)
		if not (recipients or cc or bcc):
			return

		sender = None
		message = render_notification_template(self.message, context)
		if self.sender and self.sender_email:
			sender = formataddr((self.sender, self.sender_email))

		communication = None
		if doc.doctype != "Communication":
			communication = make_communication(
				doctype=get_reference_doctype(doc),
				name=get_reference_name(doc),
				content=message,
				subject=subject,
				sender=sender,
				recipients=recipients,
				communication_medium="Email",
				send_email=False,
				attachments=attachments,
				cc=cc,
				bcc=bcc,
				communication_type="Automated Message",
			).get("name")

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			sender=sender,
			cc=cc,
			bcc=bcc,
			message=message,
			reference_doctype=get_reference_doctype(doc),
			reference_name=get_reference_name(doc),
			attachments=attachments,
			expose_recipients="header",
			print_letterhead=((attachments and attachments[0].get("print_letterhead")) or False),
			communication=communication,
		)

	def send(self, doc):
		if self.channel not in ("Slack DM", "Teams DM"):
			super().send(doc)
			return

		if frappe.flags.in_migrate:
			return

		context = build_notification_template_context(doc, alert=self)

		if self.is_standard:
			self.load_standard_properties(context)

		route_recipients, route_subject, route_message, _, route_extra = get_email_override_locals()
		apply_email_override_context(context, route_subject, route_message, route_extra)
		enqueued = False
		if not frappe.flags.in_test:
			try:
				frappe.enqueue(
					send_slack_or_teams_dm_notification,
					queue="default",
					enqueue_after_commit=True,
					job_name=f"dm-notification:{self.name}:{doc.doctype}:{doc.name}",
					notification_name=self.name,
					doc_type=doc.doctype,
					doc_name=doc.name,
					route_recipients=list(route_recipients) if route_recipients else None,
					route_subject=route_subject or None,
					route_message=route_message or None,
					route_extra=route_extra or None,
				)
				enqueued = True
			except Exception as e:
				frappe.log_error(
					title="Failed to enqueue Slack/Teams DM notification",
					message=f"{e}\n\n{frappe.get_traceback()}",
				)

		try:
			if not enqueued:
				if self.channel == "Slack DM":
					self.send_a_slack_dm_msg(doc, context)
				elif self.channel == "Teams DM":
					self.send_a_teams_dm_msg(doc, context)

			if self.send_system_notification:
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
		route_recipients, route_subject, route_message, _, route_extra = get_email_override_locals()
		apply_email_override_context(context, route_subject, route_message, route_extra)
		if frappe.are_emails_muted() and not route_recipients:
			return

		if route_recipients:
			recipients = normalize_route_recipients(list(route_recipients))
			cc, bcc = [], []
		else:
			recipients, cc, bcc = self.get_list_of_recipients(doc, context)

		if not (recipients or cc or bcc):
			return

		recipients += cc + bcc
		slack_token, show_link = frappe.db.get_value(
			"Slack Webhook URL", self.slack_webhook_url, ["webhook_url", "show_document_link"]
		)
		slack_client = WebClient(token=slack_token)
		doc_url = get_url_to_form(doc.doctype, doc.name)
		text = convert_html_to_slack_mrkdwn(render_notification_template(self.message, context))
		blocks = [
			{
				"type": "section",
				"text": {"type": "mrkdwn", "text": text},
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
					slack_client.chat_postMessage(channel=slack_user_id, blocks=blocks, text=text)
				except Exception as e:
					self.log_error("Failed to send Slack Notification", e)

	def send_a_teams_dm_msg(self, doc, context):
		"""Send a direct message via Microsoft Teams using Bot Framework REST API."""
		route_recipients, route_subject, route_message, _, route_extra = get_email_override_locals()
		apply_email_override_context(context, route_subject, route_message, route_extra)
		if route_recipients:
			recipients = list(route_recipients)
			cc, bcc = [], []
		else:
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
		message_text = render_notification_template(self.message, context)

		# Build message content
		body_content = f"<p>{message_text}</p>"
		if show_link:
			body_content += f'<p><a href="{doc_url}">Go to the document</a></p>'

		for recipient in recipients:
			try:
				messaging_client.send_dm_to_user(email=recipient, message=body_content, content_type="html")
			except Exception as e:
				self.log_error(title=TEAMS_DM_LOG_TITLE, message=teams_dm_error_body(recipient, e))

	def create_system_notification(self, doc, context):
		"""Like Notification.create_system_notification; handles None subject (e.g. Teams DM without email subject)."""
		route_recipients, route_subject, route_message, _, route_extra = get_email_override_locals()
		apply_email_override_context(context, route_subject, route_message, route_extra)

		subject = self.subject or ""
		if route_subject:
			subject = route_subject
		elif "{" in subject:
			subject = render_notification_template(self.subject or "", context)

		attachments = self.get_attachment(doc)

		if route_recipients:
			users = normalize_route_recipients(list(route_recipients))
		else:
			recipients, cc, bcc = self.get_list_of_recipients(doc, context)
			users = recipients + cc + bcc

		if not users:
			return

		log_type = "Alert"
		if route_extra and route_extra.get("notification_log_type"):
			log_type = route_extra.get("notification_log_type")

		from_user = doc.modified_by or doc.owner
		if route_extra and route_extra.get("notification_log"):
			from_user = route_extra["notification_log"].get("from_user") or from_user

		notification_doc = {
			"type": log_type,
			"document_type": get_reference_doctype(doc),
			"document_name": get_reference_name(doc),
			"subject": subject,
			"from_user": from_user,
			"email_content": render_notification_template(self.message, context),
			"attached_file": json.dumps(attachments[0]) if attachments else None,
		}
		enqueue_create_notification(users, notification_doc)
