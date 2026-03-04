# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce
from frappe.utils import get_system_timezone

from communications.communications.notifications import notify_booking


def get_context(context):
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
	context.timezone = get_system_timezone()
	context.no_cache = 1


@frappe.whitelist(allow_guest=True)
def get_events(start: str, end: str, public_calendar: str):
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
			Event.starts_on,
			Event.ends_on,
			Event.all_day,
			PublicCalendar.busy_text,
		)
		.where(
			(Event.starts_on <= end)
			& (Coalesce(Event.ends_on, Event.starts_on) >= start)
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

	if not calendar.allow_booking:
		frappe.throw(_("Booking is not enabled for this calendar"))

	event = frappe.get_doc(
		{
			"doctype": "Event",
			"subject": subject,
			"description": description,
			"starts_on": starts_on,
			"ends_on": ends_on,
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
