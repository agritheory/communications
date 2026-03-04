# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""Video conference integration for communications app"""

import frappe
from frappe import _
from frappe.model.document import Document

from .base import BaseMeetingProvider
from .zoom import ZoomProvider
from .google_meet import GoogleMeetProvider


PROVIDERS = {
	"Zoom": ZoomProvider,
	"Google Meet": GoogleMeetProvider,
}


def get_provider(provider_name: str) -> BaseMeetingProvider | None:
	"""Get a video conference provider instance"""
	if provider_name not in PROVIDERS:
		return None

	provider_class = PROVIDERS[provider_name]
	return provider_class()


def handle_video_conference(event: Document):
	"""
	Handle video conference creation/update on event validate.

	This runs on both insert and update (when event passes through validate).
	"""
	provider_name = event.get("video_conference_provider")

	if not provider_name or provider_name == "None":
		return

	provider = get_provider(provider_name)
	if not provider or not provider.is_enabled():
		return

	# Check if this is an update (meeting already exists)
	existing_meeting_id = event.get("video_conference_meeting_id")

	if existing_meeting_id and event.has_value_changed("starts_on"):
		# Update existing meeting
		try:
			provider.update_meeting(existing_meeting_id, event)
		except Exception as e:
			frappe.log_error(title=f"Failed to update {provider_name} meeting", message=str(e))
			frappe.msgprint(_("Could not update video conference meeting."))

	elif not existing_meeting_id:
		# Create new meeting
		try:
			meeting = provider.create_meeting(event)
			event.video_conference_meeting_id = meeting.get("meeting_id")
			event.video_conference_url = meeting.get("meeting_url")
			event.video_conference_data = meeting.get("meeting_data")

			# Add meeting link to description
			if event.video_conference_url:
				link_line = f"\n\nJoin the meeting: {event.video_conference_url}"
				if event.description:
					event.description = event.description + link_line
				else:
					event.description = link_line.strip()

		except Exception as e:
			frappe.log_error(title=f"Failed to create {provider_name} meeting", message=str(e))
			frappe.msgprint(_("Could not create video conference meeting."))


def delete_video_conference(event: Document):
	"""Delete video conference meeting when event is trashed"""
	provider_name = event.get("video_conference_provider")
	meeting_id = event.get("video_conference_meeting_id")

	if not provider_name or provider_name == "None" or not meeting_id:
		return

	provider = get_provider(provider_name)
	if not provider:
		return

	try:
		provider.delete_meeting(meeting_id)
	except Exception as e:
		frappe.log_error(title=f"Failed to delete {provider_name} meeting", message=str(e))
