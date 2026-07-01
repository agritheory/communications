# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""
Installation hooks for Public Calendar.
"""

import frappe

from communications.communications.email_override_defaults import (
	create_default_email_override_notifications,
)


def after_install():
	"""Create default notifications after app installation."""
	create_default_notifications()
	create_default_email_override_notifications()
	create_electronic_signature_email_template()


def after_migrate():
	"""Ensure optional records exist after schema changes."""
	create_default_email_override_notifications()
	create_electronic_signature_email_template()


def create_default_notifications():
	"""Create default Notification records for Public Calendar events."""
	notifications = [
		{
			"name": "Public Calendar - Booking Confirmation",
			"subject": "Appointment Confirmed: {{ subject }}",
			"document_type": "Event",
			"event": "Custom",
			"channel": "Email",
			"message": """<p>Hello,</p>

<p>Your appointment has been confirmed:</p>

<table style="margin: 20px 0; border-collapse: collapse;">
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Subject:</td>
		<td style="padding: 8px 0;">{{ subject }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Date:</td>
		<td style="padding: 8px 0;">{{ starts_on_formatted }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Time:</td>
		<td style="padding: 8px 0;">{{ start_time_formatted }}{% if end_time_formatted %} - {{ end_time_formatted }}{% endif %}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">With:</td>
		<td style="padding: 8px 0;">{% if is_host %}{{ guest_name }}{% else %}{{ host_name }}{% endif %}</td>
	</tr>
</table>

{% if description %}
<p><strong>Notes:</strong></p>
<p>{{ description }}</p>
{% endif %}

<p style="margin-top: 24px;">
	<a href="{{ confirm_url }}" style="display: inline-block; padding: 10px 20px; background: #22c55e; color: white; text-decoration: none; border-radius: 4px; margin-right: 8px;">Confirm Attendance</a>
	<a href="{{ decline_url }}" style="display: inline-block; padding: 10px 20px; background: #f3f4f6; color: #374151; text-decoration: none; border-radius: 4px; margin-right: 8px;">Decline</a>
	<a href="{{ cancel_url }}" style="display: inline-block; padding: 10px 20px; background: #ef4444; color: white; text-decoration: none; border-radius: 4px;">Cancel Appointment</a>
</p>

<p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
	A calendar invitation is attached to this email. Add it to your calendar to receive updates.
</p>
""",
		},
		{
			"name": "Public Calendar - Cancellation",
			"subject": "Appointment Cancelled: {{ subject }}",
			"document_type": "Event",
			"event": "Custom",
			"channel": "Email",
			"message": """<p>Hello,</p>

<p>The following appointment has been cancelled:</p>

<table style="margin: 20px 0; border-collapse: collapse;">
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Subject:</td>
		<td style="padding: 8px 0;">{{ subject }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Original Date:</td>
		<td style="padding: 8px 0;">{{ starts_on_formatted }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Original Time:</td>
		<td style="padding: 8px 0;">{{ start_time_formatted }}{% if end_time_formatted %} - {{ end_time_formatted }}{% endif %}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Cancelled by:</td>
		<td style="padding: 8px 0;">{{ cancelled_by }}</td>
	</tr>
</table>

<p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
	A calendar update is attached to remove this event from your calendar.
</p>
""",
		},
		{
			"name": "Public Calendar - Reschedule",
			"subject": "Appointment Rescheduled: {{ subject }}",
			"document_type": "Event",
			"event": "Custom",
			"channel": "Email",
			"message": """<p>Hello,</p>

<p>The following appointment has been rescheduled:</p>

<table style="margin: 20px 0; border-collapse: collapse;">
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Subject:</td>
		<td style="padding: 8px 0;">{{ subject }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">New Date:</td>
		<td style="padding: 8px 0;">{{ starts_on_formatted }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">New Time:</td>
		<td style="padding: 8px 0;">{{ start_time_formatted }}{% if end_time_formatted %} - {{ end_time_formatted }}{% endif %}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">With:</td>
		<td style="padding: 8px 0;">{% if is_host %}{{ guest_name }}{% else %}{{ host_name }}{% endif %}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Rescheduled by:</td>
		<td style="padding: 8px 0;">{{ rescheduled_by }}</td>
	</tr>
</table>

{% if description %}
<p><strong>Notes:</strong></p>
<p>{{ description }}</p>
{% endif %}

<p style="margin-top: 24px;">
	<a href="{{ confirm_url }}" style="display: inline-block; padding: 10px 20px; background: #22c55e; color: white; text-decoration: none; border-radius: 4px; margin-right: 8px;">Confirm New Time</a>
	<a href="{{ decline_url }}" style="display: inline-block; padding: 10px 20px; background: #f3f4f6; color: #374151; text-decoration: none; border-radius: 4px; margin-right: 8px;">Decline</a>
	<a href="{{ cancel_url }}" style="display: inline-block; padding: 10px 20px; background: #ef4444; color: white; text-decoration: none; border-radius: 4px;">Cancel Appointment</a>
</p>

<p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
	An updated calendar invitation is attached to this email.
</p>
""",
		},
		{
			"name": "Public Calendar - Reminder",
			"subject": "Reminder: {{ subject }} starting soon",
			"document_type": "Event",
			"event": "Custom",
			"channel": "Email",
			"message": """<p>Hello,</p>

<p>This is a reminder that your appointment is starting soon:</p>

<table style="margin: 20px 0; border-collapse: collapse;">
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Subject:</td>
		<td style="padding: 8px 0;">{{ subject }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Date:</td>
		<td style="padding: 8px 0;">{{ starts_on_formatted }}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">Time:</td>
		<td style="padding: 8px 0;">{{ start_time_formatted }}{% if end_time_formatted %} - {{ end_time_formatted }}{% endif %}</td>
	</tr>
	<tr>
		<td style="padding: 8px 16px 8px 0; font-weight: bold;">With:</td>
		<td style="padding: 8px 0;">{{ host_name }}</td>
	</tr>
</table>

{% if description %}
<p><strong>Notes:</strong></p>
<p>{{ description }}</p>
{% endif %}

<p style="margin-top: 24px;">
	<a href="{{ cancel_url }}" style="display: inline-block; padding: 10px 20px; background: #ef4444; color: white; text-decoration: none; border-radius: 4px;">Cancel Appointment</a>
</p>
""",
		},
	]

	for notification_data in notifications:
		if not frappe.db.exists("Notification", notification_data["name"]):
			doc = frappe.get_doc(
				{
					"doctype": "Notification",
					"enabled": 1,
					"is_standard": 0,
					**notification_data,
				}
			)
			doc.insert(ignore_permissions=True)


def create_electronic_signature_email_template():
	name = "Electronic Signature Request"
	if frappe.db.exists("Email Template", name):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Email Template",
			"name": name,
			"subject": "Please sign: {{ title }}",
			"use_html": 1,
			"response_html": """<p>Hello,</p>
<p>Please review and sign the following document: <strong>{{ title }}</strong></p>
{% if introduction %}{{ introduction }}{% endif %}
<p>Use the secure link below to open the signing page.</p>
<p>MAGIC_LINK</p>
<p>If you did not expect this message, you can ignore it.</p>
""",
		}
	)
	doc.insert(ignore_permissions=True)
