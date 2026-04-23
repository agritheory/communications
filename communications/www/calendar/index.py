# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce
from frappe.utils import get_datetime, get_system_timezone
import os


def get_context(context):
	route = frappe.form_dict.get("name")

	public_calendars = frappe.get_all(
		"Public Calendar",
		filters={"is_public": 1},
		fields=["name", "title", "route", "user"],
	)

	if not public_calendars:
		raise frappe.PageDoesNotExistError()

	if route:
		calendar = next((c for c in public_calendars if c.route == route), None)
		if not calendar:
			raise frappe.PageDoesNotExistError()
		context.selected_calendar = calendar.name
	else:
		context.selected_calendar = None

	context.public_calendars = public_calendars
	context.timezone = get_user_timezone()
	js_path = frappe.get_app_path("communications", "public", "js", "public_calendar.js")
	context.js_mtime = int(os.path.getmtime(js_path)) if os.path.exists(js_path) else 0
	context.no_cache = 1


@frappe.whitelist(allow_guest=True)
def get_events(start: str, end: str, public_calendar: str | None = None):
	Event = DocType("Event")
	EventParticipant = DocType("Event Participants")
	PublicCalendar = DocType("Public Calendar")
	start_dt, end_dt = convert_user_date_range_to_system(start, end)

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
			Event.subject,
			Event.starts_on,
			Event.ends_on,
			Event.all_day,
			PublicCalendar.name.as_("calendar"),
			PublicCalendar.title.as_("calendar_title"),
		)
		.where(
			(Event.starts_on <= end_dt)
			& (Coalesce(Event.ends_on, Event.starts_on) >= start_dt)
			& (PublicCalendar.is_public == 1)
			& (Event.status != "Cancelled")
		)
		.distinct()
	)

	if public_calendar:
		query = query.where(PublicCalendar.name == public_calendar)

	return query.run(as_dict=True)


def get_user_timezone() -> str:
	"""Use current user's timezone when available, else system timezone."""
	if frappe.session.user and frappe.session.user != "Guest":
		return frappe.db.get_value("User", frappe.session.user, "time_zone") or get_system_timezone()
	return get_system_timezone()


def convert_user_date_range_to_system(start_date: str, end_date: str) -> tuple:
	"""Convert user-local date boundaries to naive system-time datetimes."""
	import pytz

	user_tz = pytz.timezone(get_user_timezone())
	system_tz = pytz.timezone(get_system_timezone())

	start_local = user_tz.localize(get_datetime(f"{start_date} 00:00:00"))
	end_local = user_tz.localize(get_datetime(f"{end_date} 23:59:59"))

	start_system = start_local.astimezone(system_tz).replace(tzinfo=None)
	end_system = end_local.astimezone(system_tz).replace(tzinfo=None)
	return start_system, end_system
