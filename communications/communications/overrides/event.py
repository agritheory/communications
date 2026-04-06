# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""Event hooks for public calendar and video conferences."""

import frappe

from communications.communications.notifications import (
	get_public_calendar_for_event,
	notify_cancellation,
	notify_reschedule,
)
from communications.communications.video_conference import (
	handle_video_conference,
	delete_video_conference,
)


def validate(doc, method=None):
	"""Create or update provider meeting on validate."""
	handle_video_conference(doc)


def on_update(doc, method=None):
	"""Notify on cancel or datetime change (skip first save)."""
	if not doc.get_doc_before_save():
		return

	public_calendar = get_public_calendar_for_event(doc)
	if not public_calendar:
		return

	if doc.status == "Cancelled" and doc.has_value_changed("status"):
		handle_cancellation(doc, public_calendar)

	elif doc.has_value_changed("starts_on") or doc.has_value_changed("ends_on"):
		handle_reschedule(doc, public_calendar)


def on_trash(doc, method=None):
	"""Remove provider meeting and notify cancellation."""
	delete_video_conference(doc)

	public_calendar = get_public_calendar_for_event(doc)
	if not public_calendar:
		return

	handle_cancellation(doc, public_calendar)


def handle_cancellation(doc, public_calendar):
	"""Send cancellation notifications."""
	if not public_calendar.notify_on_cancellation:
		return

	cancelled_by_email = frappe.db.get_value("User", frappe.session.user, "email")
	notify_cancellation(doc, public_calendar, cancelled_by_email)


def handle_reschedule(doc, public_calendar):
	"""Send reschedule notifications."""
	rescheduled_by_email = frappe.db.get_value("User", frappe.session.user, "email")
	notify_reschedule(doc, public_calendar, rescheduled_by_email)
