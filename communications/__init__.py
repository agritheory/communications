# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

__version__ = "15.3.0"


# monkey patch to allow extensions in phone number
# frappe.utils.validate_phone_number = validate_phone_number
from frappe.desk.form import assign_to  # nosemgrep: frappe-monkey-patching-not-allowed
from communications.communications.overrides.assign_to import (
	custom_notify_assignment,
)  # noqa: E402

assign_to.notify_assignment = custom_notify_assignment
