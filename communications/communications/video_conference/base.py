# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""Base class for video conference providers"""

from abc import ABC, abstractmethod
from typing import Any

from frappe.model.document import Document


class BaseMeetingProvider(ABC):
	"""Abstract base class for video conference meeting providers"""

	def __init__(self, settings: Document | None = None):
		self.settings = settings or self.get_settings()

	@abstractmethod
	def get_settings(self) -> Document:
		"""Get the settings document for this provider"""
		pass

	@abstractmethod
	def create_meeting(self, event: Document) -> dict[str, Any]:
		"""
		Create a video conference meeting.

		Args:
		        event: The Event document

		Returns:
		        Dict with keys: meeting_id, meeting_url, meeting_data
		"""
		pass

	@abstractmethod
	def update_meeting(self, meeting_id: str, event: Document) -> bool:
		"""
		Update an existing video conference meeting.

		Args:
		        meeting_id: The provider's meeting ID
		        event: The Event document with updated values

		Returns:
		        True if successful, False otherwise
		"""
		pass

	@abstractmethod
	def delete_meeting(self, meeting_id: str) -> bool:
		"""
		Delete a video conference meeting.

		Args:
		        meeting_id: The provider's meeting ID

		Returns:
		        True if successful, False otherwise
		"""
		pass

	@abstractmethod
	def get_meeting_url(self, meeting_data: dict[str, Any]) -> str:
		"""
		Extract the join URL from meeting data.

		Args:
		        meeting_data: The meeting data returned by create_meeting

		Returns:
		        The URL to join the meeting
		"""
		pass

	def is_enabled(self) -> bool:
		"""Check if this provider is enabled"""
		return bool(self.settings and self.settings.get("enabled"))

	def calculate_duration(self, event: Document) -> int:
		"""Calculate meeting duration in minutes"""
		if event.ends_on and event.starts_on:
			delta = event.ends_on - event.starts_on
			return int(delta.total_seconds() / 60)
		return 30  # Default duration
