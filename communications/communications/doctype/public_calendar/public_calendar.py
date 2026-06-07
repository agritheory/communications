# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class PublicCalendar(Document):
	def validate(self):
		self.validate_working_hours()

	def after_insert(self):
		self.share_with_host()

	def validate_working_hours(self):
		if not self.working_hours:
			return

		try:
			hours = json.loads(self.working_hours)
		except json.JSONDecodeError:
			frappe.throw(frappe._("Invalid working hours format"))

		for day, blocks in hours.items():
			if not blocks:
				continue

			sorted_blocks = sorted(blocks, key=lambda b: b.get("start", ""))

			for i in range(len(sorted_blocks) - 1):
				current = sorted_blocks[i]
				next_block = sorted_blocks[i + 1]

				current_end = current.get("end", "")
				next_start = next_block.get("start", "")

				if current_end > next_start:
					frappe.throw(
						frappe._("{0}: Time blocks overlap ({1}-{2} and {3}-{4})").format(
							day.title(),
							current.get("start"),
							current_end,
							next_start,
							next_block.get("end"),
						)
					)

	def share_with_host(self):
		"""Share document with the host user for read/write access."""
		if not self.user:
			return

		# Check if already shared with this user
		existing = frappe.db.exists(
			"DocShare",
			{
				"share_doctype": self.doctype,
				"share_name": self.name,
				"user": self.user,
			},
		)

		if not existing:
			frappe.share.add_docshare(
				self.doctype,
				self.name,
				user=self.user,
				read=1,
				write=1,
				share=0,
				flags={"ignore_share_permission": True},
			)

		# If user changed, remove share from old user
		if self.has_value_changed("user") and self.get_doc_before_save():
			old_user = self.get_doc_before_save().user
			if old_user and old_user != self.user:
				frappe.share.remove(self.doctype, self.name, old_user)
