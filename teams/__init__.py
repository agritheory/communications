# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

__version__ = "15.0.0"

import frappe.utils
from teams.teams import validate_phone_number

# monkey patch to allow extensions in phone number
frappe.utils.validate_phone_number = validate_phone_number
