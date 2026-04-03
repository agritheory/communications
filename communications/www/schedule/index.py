# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import os

import pytz

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce
from frappe.utils import get_datetime, get_system_timezone

from communications.communications.notifications import notify_booking


def get_context(context):
	# Schedule booking is for authenticated users only. Guests should not see
	# calendar availability or booking UI and should receive a 404-style response.
	if frappe.session.user == "Guest":
		raise frappe.PageDoesNotExistError()

	route = frappe.form_dict.get("name")

	schedulable = frappe.get_all(
		"Public Calendar",
		filters={"allow_booking": 1},
		fields=[
			"name",
			"title",
			"route",
			"user",
			"busy_text",
			"slot_duration",
			"max_meeting_duration",
			"buffer_time",
			"min_notice_hours",
			"max_advance_days",
			"working_hours",
			"booking_dialog_title",
		],
	)

	if not schedulable:
		raise frappe.PageDoesNotExistError()

	if route:
		calendar = next((c for c in schedulable if c.route == route), None)
		if not calendar:
			raise frappe.PageDoesNotExistError()
		context.calendar = calendar
		context.parents = [{"name": _("Schedule"), "route": "/schedule"}]
	else:
		context.calendar = None
		context.parents = [{"name": _("Home"), "route": "/"}]

	context.schedulable_calendars = schedulable
	context.timezone = _get_user_timezone()
	js_path = frappe.get_app_path("communications", "public", "js", "public_calendar.js")
	context.js_mtime = int(os.path.getmtime(js_path)) if os.path.exists(js_path) else 0
	context.no_cache = 1


@frappe.whitelist(allow_guest=True)
def get_events(start: str, end: str, public_calendar: str):
	Event = DocType("Event")
	EventParticipant = DocType("Event Participants")
	PublicCalendar = DocType("Public Calendar")
	start_dt, end_dt = _convert_user_date_range_to_system(start, end)

	query = (
		frappe.qb.from_(Event)
		.join(EventParticipant)
		.on(EventParticipant.parent == Event.name)
		.join(PublicCalendar)
		.on(
			(PublicCalendar.user == EventParticipant.reference_docname)
			& (EventParticipant.reference_doctype == "User")
		)
		.select(
			Event.name,
			Event.starts_on,
			Event.ends_on,
			Event.all_day,
			PublicCalendar.busy_text,
		)
		.where(
			(Event.starts_on <= end_dt)
			& (Coalesce(Event.ends_on, Event.starts_on) >= start_dt)
			& (PublicCalendar.allow_booking == 1)
			& (PublicCalendar.name == public_calendar)
			& (Event.status != "Cancelled")
		)
		.distinct()
	)

	return query.run(as_dict=True)


@frappe.whitelist()
def book_appointment(
	public_calendar: str,
	starts_on: str,
	ends_on: str,
	subject: str,
	description: str = "",
):
	calendar = frappe.get_doc("Public Calendar", public_calendar)
	starts_on_system = _convert_user_datetime_to_system(starts_on)
	ends_on_system = _convert_user_datetime_to_system(ends_on)

	if not calendar.allow_booking:
		frappe.throw(_("Booking is not enabled for this calendar"))

	event = frappe.get_doc(
		{
			"doctype": "Event",
			"subject": subject,
			"description": description,
			"starts_on": starts_on_system,
			"ends_on": ends_on_system,
			"event_type": "Public",
			"reference_doctype": "Public Calendar",
			"reference_docname": public_calendar,
		}
	)

	event.append(
		"event_participants",
		{
			"reference_doctype": "User",
			"reference_docname": calendar.user,
			"rsvp": "Pending",
		},
	)

	event.append(
		"event_participants",
		{
			"reference_doctype": "User",
			"reference_docname": frappe.session.user,
			"rsvp": "Accepted",
		},
	)

	guest_email = frappe.db.get_value("User", frappe.session.user, "email")
	if guest_email:
		linked_parties = get_contact_links(guest_email)
		for party in linked_parties:
			event.append(
				"event_participants",
				{
					"reference_doctype": party["link_doctype"],
					"reference_docname": party["link_name"],
				},
			)

	event.insert(ignore_permissions=True)
	notify_booking(event, calendar)

	return event.name


@frappe.whitelist()
def get_available_timezones() -> list[str]:
	"""Return all valid IANA timezone strings for the timezone picker."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to continue"), frappe.PermissionError)

	from frappe.core.doctype.user.user import get_timezones

	return get_timezones().get("timezones", [])


@frappe.whitelist()
def update_my_timezone(timezone: str) -> dict:
	"""Persist the current user's timezone preference."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to continue"), frappe.PermissionError)

	timezones = get_available_timezones()
	if timezone not in timezones:
		frappe.throw(_("Please choose a valid timezone."), frappe.ValidationError)

	frappe.db.set_value("User", frappe.session.user, "time_zone", timezone)
	frappe.defaults.set_default("time_zone", timezone, frappe.session.user)
	frappe.db.commit()
	return {"timezone": timezone}


def get_contact_links(email: str) -> list[dict]:
	"""
	Get linked parties (Customer, Supplier, Lead, etc.) for a Contact by email.

	Returns list of dicts with link_doctype and link_name.
	"""
	# Find Contact with this email
	contact_name = frappe.db.get_value(
		"Contact Email",
		{"email_id": email, "parenttype": "Contact"},
		"parent",
	)

	if not contact_name:
		return []

	# Get all dynamic links from this Contact
	links = frappe.get_all(
		"Dynamic Link",
		filters={
			"parent": contact_name,
			"parenttype": "Contact",
		},
		fields=["link_doctype", "link_name"],
	)

	return links


def _get_user_timezone() -> str:
	"""Use current user's timezone when available, else system timezone."""
	if frappe.session.user and frappe.session.user != "Guest":
		return frappe.db.get_value("User", frappe.session.user, "time_zone") or get_system_timezone()
	return get_system_timezone()


def _convert_user_date_range_to_system(start_date: str, end_date: str) -> tuple:
	"""Convert user-local date boundaries to naive system-time datetimes."""
	user_tz = pytz.timezone(_get_user_timezone())
	system_tz = pytz.timezone(get_system_timezone())

	start_local = user_tz.localize(get_datetime(f"{start_date} 00:00:00"))
	end_local = user_tz.localize(get_datetime(f"{end_date} 23:59:59"))

	start_system = start_local.astimezone(system_tz).replace(tzinfo=None)
	end_system = end_local.astimezone(system_tz).replace(tzinfo=None)
	return start_system, end_system


def _convert_user_datetime_to_system(dt_str: str):
	"""Convert a user-local datetime string to naive system-time datetime."""
	user_tz = pytz.timezone(_get_user_timezone())
	system_tz = pytz.timezone(get_system_timezone())

	dt = get_datetime(dt_str)
	if dt.tzinfo is None:
		dt = user_tz.localize(dt)
	else:
		dt = dt.astimezone(user_tz)

	return dt.astimezone(system_tz).replace(tzinfo=None)
