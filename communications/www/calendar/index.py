# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce
from frappe.utils import get_system_timezone


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
	context.timezone = get_system_timezone()
	context.no_cache = 1


@frappe.whitelist(allow_guest=True)
def get_events(start: str, end: str, public_calendar: str | None = None):
	Event = DocType("Event")
	EventParticipant = DocType("Event Participants")
	PublicCalendar = DocType("Public Calendar")

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
			(Event.starts_on <= end)
			& (Coalesce(Event.ends_on, Event.starts_on) >= start)
			& (PublicCalendar.is_public == 1)
			& (Event.status != "Cancelled")
		)
		.distinct()
	)

	if public_calendar:
		query = query.where(PublicCalendar.name == public_calendar)

	return query.run(as_dict=True)
