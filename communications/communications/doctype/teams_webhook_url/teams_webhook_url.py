# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import re
from urllib.parse import quote

import requests

import frappe
from frappe import _
from frappe.core.utils import html2text
from frappe.model.document import Document

AAD_OBJECT_ID_RE = re.compile(
	r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def teams_message_text_and_format(message: str, content_type: str) -> tuple[str, str]:
	ct = (content_type or "html").lower()
	if ct == "html":
		return html2text(message, strip_links=False, wrap=False).strip(), "markdown"
	if ct in ("text", "plain"):
		return message, "plain"
	if ct == "markdown":
		return message, "markdown"
	return message, "plain"


def http_error_details(exc: BaseException) -> dict:
	r = getattr(exc, "response", None)
	if r is None:
		return {}
	try:
		return r.json()
	except Exception:
		return {"status_code": r.status_code, "text": r.text}


class TeamsMessagingError(Exception):
	def __init__(self, message: str, details: dict | None = None):
		details = details or {}
		self.message = message
		self.details = details
		super().__init__(message, details)


class ConversationCreationError(TeamsMessagingError):
	pass


class MessageSendError(TeamsMessagingError):
	pass


class TokenAcquisitionError(TeamsMessagingError):
	pass


class TeamsMessagingClient:
	DEFAULT_SERVICE_URL = "https://smba.trafficmanager.net/teams/"
	BOT_TOKEN_CACHE_TTL = 3300
	GRAPH_TOKEN_CACHE_TTL = 3300
	USER_ID_CACHE_TTL = 86400

	def __init__(
		self,
		bot_app_id: str,
		bot_app_secret: str,
		tenant_id: str,
		tenant_domain: str | None = None,
		service_url: str | None = None,
	):
		self.bot_app_id = bot_app_id
		self.bot_app_secret = bot_app_secret
		self.tenant_id = tenant_id
		self.tenant_domain = tenant_domain
		self.service_url = service_url or self.DEFAULT_SERVICE_URL

	def get_bot_token(self) -> str:
		cache_key = f"teams_bot_token:{self.bot_app_id}"
		cached = frappe.cache().get_value(cache_key)
		if cached:
			return cached

		data = {
			"grant_type": "client_credentials",
			"client_id": self.bot_app_id,
			"client_secret": self.bot_app_secret,
			"scope": "https://api.botframework.com/.default",
		}
		token_urls = [
			f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
			"https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token",
		]
		for index, token_url in enumerate(token_urls):
			response = requests.post(token_url, data=data, timeout=30)
			if response.ok:
				token = response.json()["access_token"]
				frappe.cache().set_value(cache_key, token, expires_in_sec=self.BOT_TOKEN_CACHE_TTL)
				return token
			try:
				details = response.json()
			except Exception:
				details = {"status_code": response.status_code, "text": response.text}
			error_codes = details.get("error_codes") or []
			if index == 0 and 700016 in error_codes and len(token_urls) > 1:
				continue
			raise TokenAcquisitionError(
				f"Failed to acquire Bot Framework token: {details.get('error_description', response.text)}",
				details,
			)
		raise TokenAcquisitionError("Failed to acquire Bot Framework token", {})

	def get_graph_token(self) -> str:
		cache_key = f"teams_graph_token:{self.bot_app_id}"
		cached = frappe.cache().get_value(cache_key)
		if cached:
			return cached
		token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
		response = requests.post(
			token_url,
			data={
				"grant_type": "client_credentials",
				"client_id": self.bot_app_id,
				"client_secret": self.bot_app_secret,
				"scope": "https://graph.microsoft.com/.default",
			},
			timeout=30,
		)
		if not response.ok:
			try:
				details = response.json()
			except Exception:
				details = {"status_code": response.status_code, "text": response.text}
			raise TokenAcquisitionError(
				f"Failed to acquire Microsoft Graph token: {details.get('error_description', response.text)}",
				details,
			)
		token = response.json()["access_token"]
		frappe.cache().set_value(cache_key, token, expires_in_sec=self.GRAPH_TOKEN_CACHE_TTL)
		return token

	def resolve_aad_object_id(self, email: str) -> str:
		token = self.get_graph_token()
		headers = {"Authorization": f"Bearer {token}"}
		url = f"https://graph.microsoft.com/v1.0/users/{quote(email, safe='')}"
		response = requests.get(url, headers=headers, timeout=30)

		if response.ok:
			oid = response.json().get("id")
			if oid:
				return oid
			raise ConversationCreationError("Graph user missing id", {})

		if response.status_code == 404:
			esc = email.replace("'", "''")
			flt = f"mail eq '{esc}' or userPrincipalName eq '{esc}'"
			list_resp = requests.get(
				"https://graph.microsoft.com/v1.0/users",
				headers=headers,
				params={"$filter": flt, "$select": "id"},
				timeout=30,
			)
			if list_resp.ok:
				values = list_resp.json().get("value") or []
				if len(values) == 1 and values[0].get("id"):
					return values[0]["id"]
				if len(values) == 0:
					raise ConversationCreationError(f"No Entra user for {email!r}", {"filter": flt})
				raise ConversationCreationError(f"Multiple Entra users for {email!r}", {"count": len(values)})
			response = list_resp

		try:
			details = response.json()
		except Exception:
			details = {"status_code": response.status_code, "text": response.text}
		raise ConversationCreationError(
			"Entra user lookup failed (Graph User.Read.All + admin consent, or Social ID teams GUID). "
			f"{details}",
			details,
		)

	def teams_bot_channel_account_id(self) -> str:
		bid = (self.bot_app_id or "").strip()
		return bid if bid.startswith("28:") else f"28:{bid}"

	def get_user_id(self, email: str) -> str:
		social_id = frappe.db.get_value("Social ID", {"parent": email, "provider": "teams"}, "userid")
		if social_id and AAD_OBJECT_ID_RE.match(social_id.strip()):
			return social_id.strip()

		cache_key = f"teams_user_id:{email}"
		cached_id = frappe.cache().get_value(cache_key)
		if cached_id and AAD_OBJECT_ID_RE.match(str(cached_id).strip()):
			return str(cached_id).strip()

		aad_id = self.resolve_aad_object_id(email)
		frappe.cache().set_value(cache_key, aad_id, expires_in_sec=self.USER_ID_CACHE_TTL)
		return aad_id

	def create_conversation(self, user_id: str) -> dict:
		token = self.get_bot_token()
		headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
		body = {
			"bot": {"id": self.teams_bot_channel_account_id()},
			"members": [{"id": user_id, "aadObjectId": user_id}],
			"channelData": {
				"tenant": {"id": self.tenant_id},
				"defaultUsersHistoryDisclosed": True,
			},
		}
		try:
			response = requests.post(
				f"{self.service_url}v3/conversations", headers=headers, json=body, timeout=30
			)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.RequestException as e:
			raise ConversationCreationError(
				f"Failed to create conversation with user {user_id}: {e}", http_error_details(e)
			)

	def send_message_to_conversation(
		self,
		conversation_id: str,
		message: str,
		service_url: str | None = None,
		content_type: str = "html",
	) -> dict:
		token = self.get_bot_token()
		headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
		url = service_url or self.service_url
		text, text_format = teams_message_text_and_format(message, content_type)
		try:
			response = requests.post(
				f"{url}v3/conversations/{conversation_id}/activities",
				headers=headers,
				json={"type": "message", "text": text, "textFormat": text_format},
				timeout=30,
			)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.RequestException as e:
			raise MessageSendError(
				f"Failed to send message to conversation {conversation_id}: {e}", http_error_details(e)
			)

	def send_dm_to_user(self, email: str, message: str, content_type: str = "html") -> dict:
		user_id = self.get_user_id(email)
		conversation = self.create_conversation(user_id)
		conversation_id = conversation.get("id")
		service_url = conversation.get("serviceUrl", self.service_url)
		if not conversation_id:
			raise ConversationCreationError("Conversation creation returned no ID", conversation)
		return self.send_message_to_conversation(
			conversation_id, message, service_url, content_type=content_type
		)


class TeamsWebhookURL(Document):
	def validate(self):
		if (self.bot_app_id or self.bot_app_secret) and not (
			self.bot_app_id and self.bot_app_secret and self.tenant_id
		):
			frappe.throw(_("Bot Framework requires Bot App ID, Bot App Secret, and Tenant ID"))

	def get_messaging_client(self) -> TeamsMessagingClient:
		return TeamsMessagingClient(
			bot_app_id=self.bot_app_id,
			bot_app_secret=self.get_password("bot_app_secret"),
			tenant_id=self.tenant_id,
			tenant_domain=self.tenant_domain,
			service_url=self.service_url or TeamsMessagingClient.DEFAULT_SERVICE_URL,
		)
