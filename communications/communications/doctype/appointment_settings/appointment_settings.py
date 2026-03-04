# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""Appointment Settings doctype"""

from frappe.model.document import Document


class AppointmentSettings(Document):
	"""Settings for video conference integrations"""

	doctype = "Appointment Settings"
