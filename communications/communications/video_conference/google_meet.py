# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""Google Meet video conference provider implementation"""

from typing import Any

import frappe
from frappe.model.document import Document

from .base import BaseMeetingProvider


class GoogleMeetProvider(BaseMeetingProvider):
	"""Google Meet provider using Google Calendar integration"""

	def _get_settings(self) -> Document:
		return frappe.get_single("Appointment Settings")

	def is_enabled(self) -> bool:
		return bool(self.settings.enable_google_meet)

	def create_meeting(self, event: Document) -> dict[str, Any]:
		"""
		Create Google Meet conference data.

		Note: This returns conference data to be included in the Google Calendar
		event creation. The actual meet link is returned after the event is created.
		"""
		return {
			"meeting_id": None,  # Set after calendar event creation
			"meeting_url": None,  # Set after calendar event creation
			"meeting_data": {
				"conferenceData": {
					"createRequest": {
						"requestId": f"communications-{event.name or frappe.generate_hash()}",
						"conferenceSolutionKey": {"type": "hangoutsMeet"},
					}
				}
			},
		}

	def update_meeting(self, meeting_id: str, event: Document) -> bool:
		"""
		Google Meet links are updated automatically when the calendar event is updated.
		No separate API call needed.
		"""
		return True

	def delete_meeting(self, meeting_id: str) -> bool:
		"""
		Google Meet links are deleted automatically when the calendar event is deleted.
		No separate API call needed.
		"""
		return True

	def get_meeting_url(self, meeting_data: dict[str, Any]) -> str:
		"""Extract the Google Meet URL from meeting data"""
		return meeting_data.get("hangoutLink", "")
