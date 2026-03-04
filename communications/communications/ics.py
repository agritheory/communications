# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""
ICS (iCalendar) generation utilities.

Generates RFC 5545 compliant iCalendar files for event invitations,
updates, and cancellations with RSVP support.
"""

from datetime import datetime
from typing import Literal

import frappe
from frappe.utils import get_datetime


def generate_ics(
	event: "frappe.Document",
	method: Literal["REQUEST", "CANCEL", "REPLY"] = "REQUEST",
	organizer_email: str | None = None,
	organizer_name: str | None = None,
	attendees: list[dict] | None = None,
	sequence: int = 0,
) -> str:
	"""
	Generate an ICS file for an event.

	Args:
	        event: Event document
	        method: ICS method - REQUEST (invite), CANCEL, or REPLY
	        organizer_email: Email of the organizer
	        organizer_name: Display name of the organizer
	        attendees: List of dicts with keys: email, name, status (NEEDS-ACTION, ACCEPTED, DECLINED, TENTATIVE)
	        sequence: ICS sequence number (increment for updates/cancellations)

	Returns:
	        ICS file content as string
	"""
	lines = [
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		f"PRODID:-//Frappe//{frappe.local.site}//EN",
		"CALSCALE:GREGORIAN",
		f"METHOD:{method}",
	]

	lines.extend(
		_generate_vevent(event, method, organizer_email, organizer_name, attendees, sequence)
	)

	lines.append("END:VCALENDAR")

	return "\r\n".join(lines)


def _generate_vevent(
	event: "frappe.Document",
	method: str,
	organizer_email: str | None,
	organizer_name: str | None,
	attendees: list[dict] | None,
	sequence: int,
) -> list[str]:
	"""Generate VEVENT component lines."""
	lines = ["BEGIN:VEVENT"]

	# UID - deterministic identifier from event name and site
	uid = f"{event.name}@{frappe.local.site}"
	lines.append(f"UID:{uid}")

	# Sequence number for updates/cancellations
	lines.append(f"SEQUENCE:{sequence}")

	# Timestamps
	dtstamp = _format_datetime_utc(datetime.utcnow())
	lines.append(f"DTSTAMP:{dtstamp}")

	# Start/End times
	starts_on = get_datetime(event.starts_on)
	if event.all_day:
		lines.append(f"DTSTART;VALUE=DATE:{starts_on.strftime('%Y%m%d')}")
		if event.ends_on:
			ends_on = get_datetime(event.ends_on)
			lines.append(f"DTEND;VALUE=DATE:{ends_on.strftime('%Y%m%d')}")
	else:
		lines.append(f"DTSTART:{_format_datetime_utc(starts_on)}")
		if event.ends_on:
			ends_on = get_datetime(event.ends_on)
			lines.append(f"DTEND:{_format_datetime_utc(ends_on)}")

	# Summary and description
	lines.append(f"SUMMARY:{_escape_ics_text(event.subject or 'Meeting')}")
	if event.description:
		lines.append(f"DESCRIPTION:{_escape_ics_text(event.description)}")

	# Location (if any)
	if event.get("location"):
		lines.append(f"LOCATION:{_escape_ics_text(event.location)}")

	# Status
	if method == "CANCEL":
		lines.append("STATUS:CANCELLED")
	else:
		lines.append("STATUS:CONFIRMED")

	# Organizer
	if organizer_email:
		if organizer_name:
			lines.append(f"ORGANIZER;CN={_escape_ics_param(organizer_name)}:mailto:{organizer_email}")
		else:
			lines.append(f"ORGANIZER:mailto:{organizer_email}")

	# Attendees
	if attendees:
		for attendee in attendees:
			lines.append(_format_attendee(attendee))

	# Transparency
	lines.append("TRANSP:OPAQUE")

	lines.append("END:VEVENT")
	return lines


def _format_attendee(attendee: dict) -> str:
	"""Format an ATTENDEE line with proper parameters."""
	email = attendee.get("email", "")
	name = attendee.get("name", "")
	status = attendee.get("status", "NEEDS-ACTION")
	rsvp = attendee.get("rsvp", True)

	parts = ["ATTENDEE"]
	parts.append("ROLE=REQ-PARTICIPANT")
	parts.append(f"PARTSTAT={status}")
	if rsvp:
		parts.append("RSVP=TRUE")
	if name:
		parts.append(f"CN={_escape_ics_param(name)}")

	return f"{';'.join(parts)}:mailto:{email}"


def _format_datetime_utc(dt: datetime) -> str:
	"""Format datetime as ICS UTC timestamp (YYYYMMDDTHHMMSSZ)."""
	if dt.tzinfo is not None:
		import calendar

		timestamp = calendar.timegm(dt.utctimetuple())
		dt = datetime.utcfromtimestamp(timestamp)
	return dt.strftime("%Y%m%dT%H%M%SZ")


def _escape_ics_text(text: str) -> str:
	"""Escape special characters in ICS text values."""
	if not text:
		return ""
	# RFC 5545: escape backslash, semicolon, comma, and newlines
	text = text.replace("\\", "\\\\")
	text = text.replace(";", "\\;")
	text = text.replace(",", "\\,")
	text = text.replace("\r\n", "\\n")
	text = text.replace("\n", "\\n")
	text = text.replace("\r", "\\n")
	return text


def _escape_ics_param(text: str) -> str:
	"""Escape parameter values (CN, etc). Quote if contains special chars."""
	if not text:
		return ""
	if any(c in text for c in [",", ";", ":", '"']):
		text = text.replace('"', '\\"')
		return f'"{text}"'
	return text


def generate_ics_attachment(
	event: "frappe.Document",
	method: Literal["REQUEST", "CANCEL", "REPLY"] = "REQUEST",
	organizer_email: str | None = None,
	organizer_name: str | None = None,
	attendees: list[dict] | None = None,
	filename: str | None = None,
	sequence: int = 0,
) -> dict:
	"""
	Generate an ICS file as an email attachment dict.

	Returns a dict suitable for frappe.sendmail's attachments parameter.
	"""
	content = generate_ics(event, method, organizer_email, organizer_name, attendees, sequence)

	if not filename:
		if method == "CANCEL":
			filename = "cancellation.ics"
		else:
			filename = "invite.ics"

	return {
		"fname": filename,
		"fcontent": content,
		"content_type": "text/calendar; method=" + method,
	}
