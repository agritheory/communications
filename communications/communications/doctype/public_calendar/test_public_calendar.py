# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPublicCalendar(FrappeTestCase):
	def setUp(self):
		# Create a test user if not exists
		if not frappe.db.exists("User", "test_calendar_user@example.com"):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": "test_calendar_user@example.com",
					"first_name": "Test Calendar",
					"last_name": "User",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			)
			user.insert(ignore_permissions=True)

	def test_create_public_calendar(self):
		"""Test creating a basic public calendar"""
		calendar = frappe.get_doc(
			{
				"doctype": "Public Calendar",
				"title": "Test Calendar",
				"user": "test_calendar_user@example.com",
				"route": "test-calendar-001",
				"is_public": 1,
				"enabled": 1,
			}
		)
		calendar.insert(ignore_permissions=True)

		self.assertEqual(calendar.title, "Test Calendar")
		self.assertEqual(calendar.user, "test_calendar_user@example.com")
		self.assertEqual(calendar.route, "test-calendar-001")

		# Cleanup
		calendar.delete(ignore_permissions=True)

	def test_working_hours_validation(self):
		"""Test that overlapping time blocks are rejected"""
		import json

		calendar = frappe.get_doc(
			{
				"doctype": "Public Calendar",
				"title": "Test Calendar Overlap",
				"user": "test_calendar_user@example.com",
				"route": "test-calendar-overlap",
				"working_hours": json.dumps(
					{
						"monday": [
							{"start": "09:00", "end": "12:00"},
							{"start": "11:00", "end": "14:00"},  # Overlaps with previous
						]
					}
				),
			}
		)

		with self.assertRaises(frappe.ValidationError):
			calendar.save()

	def test_share_with_host(self):
		"""Test that calendar is shared with host user on creation"""
		calendar = frappe.get_doc(
			{
				"doctype": "Public Calendar",
				"title": "Test Calendar Share",
				"user": "test_calendar_user@example.com",
				"route": "test-calendar-share",
			}
		)
		calendar.insert(ignore_permissions=True)

		# Check if share exists
		share_exists = frappe.db.exists(
			"DocShare",
			{
				"share_doctype": "Public Calendar",
				"share_name": calendar.name,
				"user": "test_calendar_user@example.com",
			},
		)

		self.assertTrue(share_exists)

		# Cleanup
		calendar.delete(ignore_permissions=True)
