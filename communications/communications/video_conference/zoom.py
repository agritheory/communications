# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""Zoom video conference provider implementation"""

import base64
from typing import Any

import requests

import frappe
from frappe import _
from frappe.model.document import Document

from .base import BaseMeetingProvider


class ZoomProvider(BaseMeetingProvider):
	"""Zoom meeting provider using Server-to-Server OAuth"""

	API_BASE_URL = "https://api.zoom.us/v2"
	TOKEN_URL = "https://zoom.us/oauth/token"

	def get_settings(self) -> Document:
		return frappe.get_single("Appointment Settings")

	def is_enabled(self) -> bool:
		return bool(self.settings.enable_zoom)

	def get_client(self) -> requests.Session:
		"""Get authenticated Zoom API client"""
		access_token = self.settings.get_password("zoom_access_token")

		if not access_token:
			access_token = self.refresh_token()

		session = requests.Session()
		session.headers.update(
			{"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
		)
		return session

	def refresh_token(self) -> str:
		"""Refresh Zoom access token using Server-to-Server OAuth"""
		client_id = self.settings.zoom_client_id
		client_secret = self.settings.get_password("zoom_client_secret")
		account_id = self.settings.zoom_account_id

		if not all([client_id, client_secret, account_id]):
			frappe.throw(_("Zoom credentials not configured in Appointment Settings"))

		auth_string = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

		response = requests.post(
			self.TOKEN_URL,
			data={"grant_type": "account_credentials", "account_id": account_id},
			headers={"Authorization": f"Basic {auth_string}"},
		)
		response.raise_for_status()

		token_data = response.json()
		access_token = token_data["access_token"]

		# Store the new token
		self.settings.zoom_access_token = access_token
		self.settings.save(ignore_permissions=True)

		return access_token

	def create_meeting(self, event: Document) -> dict[str, Any]:
		"""Create a Zoom meeting for the event"""
		client = self.get_client()

		# Get the Zoom user email - from event or settings
		user_email = event.get("zoom_user_email") or self.settings.zoom_user_email
		if not user_email:
			frappe.throw(_("Zoom user email not configured"))

		duration = self.calculate_duration(event)

		data = {
			"topic": event.subject,
			"type": 2,  # Scheduled meeting
			"start_time": event.starts_on.isoformat(),
			"duration": duration,
			"timezone": frappe.defaults.get_user_default("timezone") or "UTC",
			"agenda": event.description or "",
		}

		response = client.post(f"{self.API_BASE_URL}/users/{user_email}/meetings", json=data)

		# Handle token expiration
		if response.status_code == 401:
			self.refresh_token()
			client = self.get_client()
			response = client.post(f"{self.API_BASE_URL}/users/{user_email}/meetings", json=data)

		response.raise_for_status()
		meeting_data = response.json()

		return {
			"meeting_id": str(meeting_data["id"]),
			"meeting_url": meeting_data["join_url"],
			"meeting_data": meeting_data,
		}

	def update_meeting(self, meeting_id: str, event: Document) -> bool:
		"""Update an existing Zoom meeting"""
		client = self.get_client()
		duration = self.calculate_duration(event)

		data = {
			"topic": event.subject,
			"type": 2,
			"start_time": event.starts_on.isoformat(),
			"duration": duration,
			"timezone": frappe.defaults.get_user_default("timezone") or "UTC",
			"agenda": event.description or "",
		}

		response = client.patch(f"{self.API_BASE_URL}/meetings/{meeting_id}", json=data)

		# Handle token expiration
		if response.status_code == 401:
			self.refresh_token()
			client = self.get_client()
			response = client.patch(f"{self.API_BASE_URL}/meetings/{meeting_id}", json=data)

		return response.ok

	def delete_meeting(self, meeting_id: str) -> bool:
		"""Delete a Zoom meeting"""
		client = self.get_client()

		response = client.delete(f"{self.API_BASE_URL}/meetings/{meeting_id}")

		# Meeting not found is OK (already deleted)
		if response.status_code == 404:
			return True

		# Handle token expiration
		if response.status_code == 401:
			self.refresh_token()
			client = self.get_client()
			response = client.delete(f"{self.API_BASE_URL}/meetings/{meeting_id}")

		return response.ok

	def get_meeting_url(self, meeting_data: dict[str, Any]) -> str:
		"""Extract the join URL from meeting data"""
		return meeting_data.get("join_url", "")
