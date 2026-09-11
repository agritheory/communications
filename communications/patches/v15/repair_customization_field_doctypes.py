# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

"""Restore dt and clear is_system_generated on Event video conference Custom Fields."""

import frappe


def execute():
	for name in (
		"Event-video_conference_provider",
		"Event-video_conference_meeting_id",
		"Event-video_conference_url",
		"Event-video_conference_data",
	):
		if not frappe.db.exists("Custom Field", name):
			continue
		frappe.db.set_value(
			"Custom Field",
			name,
			{"dt": "Event", "is_system_generated": 0},
			update_modified=False,
		)
