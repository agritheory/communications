# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""RFC 5545 iCalendar text and email attachments for events."""

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
	"""Return VCALENDAR text for an Event (METHOD + optional organizer/attendees)."""
	lines = [
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		f"PRODID:-//Frappe//{frappe.local.site}//EN",
		"CALSCALE:GREGORIAN",
		f"METHOD:{method}",
	]

	lines.extend(
		generate_vevent_lines(event, method, organizer_email, organizer_name, attendees, sequence)
	)

	lines.append("END:VCALENDAR")

	return "\r\n".join(lines)


def generate_vevent_lines(
	event: "frappe.Document",
	method: str,
	organizer_email: str | None,
	organizer_name: str | None,
	attendees: list[dict] | None,
	sequence: int,
) -> list[str]:
	"""Generate VEVENT component lines."""
	lines = ["BEGIN:VEVENT"]

	uid = f"{event.name}@{frappe.local.site}"
	lines.append(f"UID:{uid}")

	lines.append(f"SEQUENCE:{sequence}")

	dtstamp = format_datetime_utc(datetime.utcnow())
	lines.append(f"DTSTAMP:{dtstamp}")

	starts_on = get_datetime(event.starts_on)
	if event.all_day:
		lines.append(f"DTSTART;VALUE=DATE:{starts_on.strftime('%Y%m%d')}")
		if event.ends_on:
			ends_on = get_datetime(event.ends_on)
			lines.append(f"DTEND;VALUE=DATE:{ends_on.strftime('%Y%m%d')}")
	else:
		lines.append(f"DTSTART:{format_datetime_utc(starts_on)}")
		if event.ends_on:
			ends_on = get_datetime(event.ends_on)
			lines.append(f"DTEND:{format_datetime_utc(ends_on)}")

	lines.append(f"SUMMARY:{escape_ics_text(event.subject or 'Meeting')}")
	if event.description:
		lines.append(f"DESCRIPTION:{escape_ics_text(event.description)}")

	if event.get("location"):
		lines.append(f"LOCATION:{escape_ics_text(event.location)}")

	if method == "CANCEL":
		lines.append("STATUS:CANCELLED")
	else:
		lines.append("STATUS:CONFIRMED")

	if organizer_email:
		if organizer_name:
			lines.append(f"ORGANIZER;CN={escape_ics_param(organizer_name)}:mailto:{organizer_email}")
		else:
			lines.append(f"ORGANIZER:mailto:{organizer_email}")

	if attendees:
		for attendee in attendees:
			lines.append(format_attendee_line(attendee))

	lines.append("TRANSP:OPAQUE")

	lines.append("END:VEVENT")
	return lines


def format_attendee_line(attendee: dict) -> str:
	"""One ATTENDEE line for ICS."""
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
		parts.append(f"CN={escape_ics_param(name)}")

	return f"{';'.join(parts)}:mailto:{email}"


def format_datetime_utc(dt: datetime) -> str:
	"""Format datetime as ICS UTC timestamp (YYYYMMDDTHHMMSSZ)."""
	if dt.tzinfo is not None:
		import calendar

		timestamp = calendar.timegm(dt.utctimetuple())
		dt = datetime.utcfromtimestamp(timestamp)
	return dt.strftime("%Y%m%dT%H%M%SZ")


def escape_ics_text(text: str) -> str:
	"""ICS TEXT value escaping."""
	if not text:
		return ""
	text = text.replace("\\", "\\\\")
	text = text.replace(";", "\\;")
	text = text.replace(",", "\\,")
	text = text.replace("\r\n", "\\n")
	text = text.replace("\n", "\\n")
	text = text.replace("\r", "\\n")
	return text


def escape_ics_param(text: str) -> str:
	"""ICS parameter (e.g. CN) quoting."""
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
	"""Attachment dict for frappe.sendmail."""
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
