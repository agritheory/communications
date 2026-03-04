# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""Unit tests for video conference integration"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import frappe
import pytest

from communications.communications.video_conference import (
	PROVIDERS,
	delete_video_conference,
	get_provider,
	handle_video_conference,
)
from communications.communications.video_conference.base import BaseMeetingProvider
from communications.communications.video_conference.google_meet import GoogleMeetProvider
from communications.communications.video_conference.zoom import ZoomProvider


def test_providers_dict_contains_expected_providers():
	"""Test that PROVIDERS dict contains Zoom and Google Meet"""
	assert "Zoom" in PROVIDERS
	assert "Google Meet" in PROVIDERS
	assert PROVIDERS["Zoom"] == ZoomProvider
	assert PROVIDERS["Google Meet"] == GoogleMeetProvider


def test_get_provider_returns_zoom_instance():
	"""Test get_provider returns ZoomProvider instance"""
	provider = get_provider("Zoom")
	assert isinstance(provider, ZoomProvider)
	assert isinstance(provider, BaseMeetingProvider)


def test_get_provider_returns_google_meet_instance():
	"""Test get_provider returns GoogleMeetProvider instance"""
	provider = get_provider("Google Meet")
	assert isinstance(provider, GoogleMeetProvider)
	assert isinstance(provider, BaseMeetingProvider)


def test_get_provider_returns_none_for_invalid_provider():
	"""Test get_provider returns None for unknown provider"""
	provider = get_provider("Unknown Provider")
	assert provider is None


def test_zoom_provider_calculate_duration():
	"""Test duration calculation from event times"""
	provider = ZoomProvider.__new__(ZoomProvider)

	event = frappe._dict(
		{"starts_on": datetime(2025, 3, 2, 10, 0), "ends_on": datetime(2025, 3, 2, 11, 30)}
	)

	duration = provider._calculate_duration(event)
	assert duration == 90  # 1.5 hours = 90 minutes


def test_zoom_provider_calculate_duration_no_end_time():
	"""Test duration returns default when no end time"""
	provider = ZoomProvider.__new__(ZoomProvider)

	event = frappe._dict({"starts_on": datetime(2025, 3, 2, 10, 0), "ends_on": None})

	duration = provider._calculate_duration(event)
	assert duration == 30  # Default duration


@patch("communications.communications.video_conference.zoom.requests.post")
@patch("communications.communications.video_conference.zoom.frappe.get_single")
def test_zoom_refresh_token(mock_get_single, mock_post):
	"""Test Zoom token refresh"""
	settings = MagicMock()
	settings.zoom_client_id = "test_client_id"
	settings.get_password.return_value = "test_client_secret"
	settings.zoom_account_id = "test_account_id"
	settings.zoom_access_token = None
	mock_get_single.return_value = settings

	mock_response = MagicMock()
	mock_response.json.return_value = {"access_token": "new_test_token"}
	mock_response.raise_for_status = MagicMock()
	mock_post.return_value = mock_response

	provider = ZoomProvider(settings)
	token = provider._refresh_token()

	assert token == "new_test_token"
	settings.save.assert_called_once()


def test_google_meet_create_meeting_returns_conference_data():
	"""Test Google Meet create_meeting returns conference data structure"""
	provider = GoogleMeetProvider.__new__(GoogleMeetProvider)
	provider.settings = MagicMock()

	event = frappe._dict({"name": "test-event-001"})

	result = provider.create_meeting(event)

	assert "meeting_id" in result
	assert "meeting_url" in result
	assert "meeting_data" in result
	assert "conferenceData" in result["meeting_data"]
	assert "createRequest" in result["meeting_data"]["conferenceData"]


def test_google_meet_update_meeting_returns_true():
	"""Test Google Meet update_meeting always returns True"""
	provider = GoogleMeetProvider.__new__(GoogleMeetProvider)
	provider.settings = MagicMock()

	result = provider.update_meeting("any-meeting-id", MagicMock())
	assert result is True


def test_google_meet_delete_meeting_returns_true():
	"""Test Google Meet delete_meeting always returns True"""
	provider = GoogleMeetProvider.__new__(GoogleMeetProvider)
	provider.settings = MagicMock()

	result = provider.delete_meeting("any-meeting-id")
	assert result is True


def test_google_meet_get_meeting_url_extracts_hangout_link():
	"""Test get_meeting_url extracts hangoutLink"""
	provider = GoogleMeetProvider.__new__(GoogleMeetProvider)

	meeting_data = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}

	url = provider.get_meeting_url(meeting_data)
	assert url == "https://meet.google.com/abc-defg-hij"


def test_google_meet_get_meeting_url_returns_empty_if_no_link():
	"""Test get_meeting_url returns empty string if no hangoutLink"""
	provider = GoogleMeetProvider.__new__(GoogleMeetProvider)

	meeting_data = {}

	url = provider.get_meeting_url(meeting_data)
	assert url == ""


def test_handle_video_conference_skips_if_no_provider():
	"""Test that handle_video_conference skips if no provider selected"""
	event = frappe._dict({"video_conference_provider": None})
	handle_video_conference(event)


def test_handle_video_conference_skips_if_provider_is_none_string():
	"""Test that handle_video_conference skips if provider is 'None'"""
	event = frappe._dict({"video_conference_provider": "None"})
	handle_video_conference(event)


@patch("communications.communications.video_conference.get_provider")
def test_handle_video_conference_skips_if_provider_not_enabled(mock_get_provider):
	"""Test that handle_video_conference skips if provider not enabled"""
	mock_provider = MagicMock()
	mock_provider.is_enabled.return_value = False
	mock_get_provider.return_value = mock_provider

	event = frappe._dict({"video_conference_provider": "Zoom"})

	handle_video_conference(event)

	mock_provider.create_meeting.assert_not_called()


def test_delete_video_conference_skips_if_no_provider():
	"""Test that delete_video_conference skips if no provider"""
	event = frappe._dict({"video_conference_provider": None, "video_conference_meeting_id": "123"})
	delete_video_conference(event)


def test_delete_video_conference_skips_if_no_meeting_id():
	"""Test that delete_video_conference skips if no meeting ID"""
	event = frappe._dict({"video_conference_provider": "Zoom", "video_conference_meeting_id": None})
	delete_video_conference(event)


@patch("communications.communications.video_conference.get_provider")
def test_delete_video_conference_calls_provider_delete(mock_get_provider):
	"""Test that delete_video_conference calls provider delete_meeting"""
	mock_provider = MagicMock()
	mock_get_provider.return_value = mock_provider

	event = frappe._dict(
		{"video_conference_provider": "Zoom", "video_conference_meeting_id": "meeting-123"}
	)

	delete_video_conference(event)

	mock_provider.delete_meeting.assert_called_once_with("meeting-123")
