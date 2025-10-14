# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from urllib.parse import urlencode
from typing import Any
import frappe
from frappe.utils import get_url


class DigestBuilder:
	@staticmethod
	def generate_report_url(user: str, doctype: str, items: list[dict]) -> str:
		try:
			doc_names = [item.get("reference_name") for item in items if item.get("reference_name")]
			params = {"allocated_to": user, "status": "Open", "reference_type": doctype}
			if doc_names:
				params["reference_name"] = json.dumps(["in", doc_names])
			return get_url(f"/app/todo?{urlencode(params)}")
		except Exception as e:
			frappe.log_error(f"Error generating report URL: {str(e)}", "Report Generator")
			return get_url(f"/app/todo?allocated_to={user}&status=Open")

	@staticmethod
	def build_digest(user: str, notifications: list[dict]) -> dict:
		try:
			grouped: dict[str, list[dict[str, Any]]] = {}
			for notification in notifications:
				doctype = notification["reference_doctype"]
				if doctype not in grouped:
					grouped[doctype] = []
				grouped[doctype].append(notification)

			sections = []
			total_count = len(notifications)

			for doctype, items in grouped.items():
				report_url = DigestBuilder.generate_report_url(user, doctype, items)
				section = {
					"doctype": doctype,
					"count": len(items),
					"items": DigestBuilder._format_items(items),
					"report_url": report_url,
				}
				sections.append(section)

			return {
				"user": user,
				"total_count": total_count,
				"sections": sections,
				"subject": f"You have {total_count} new assignment{'s' if total_count > 1 else ''}",
				"html": DigestBuilder._render_html(user, total_count, sections),
			}

		except Exception as e:
			frappe.log_error(f"Error building digest: {str(e)}", "Digest Builder")
			raise

	@staticmethod
	def _format_items(items: list[dict]) -> list[dict]:
		formatted = []

		for item in items:
			try:
				doc = frappe.get_doc("Assignment Notification Queue", item["name"])
				doc_url = get_url(f"/app/{frappe.scrub(doc.reference_doctype)}/{doc.reference_name}")
				formatted_item = {
					"name": doc.reference_name,
					"url": doc_url,
					"description": doc.description or "",
					"assigned_by": doc.assigned_by,
					"assignment_date": doc.assignment_date,
				}
				formatted.append(formatted_item)
			except Exception as e:
				frappe.log_error(f"Error formatting item {item.get('name')}: {str(e)}", "Digest Builder")
				continue

		return formatted

	@staticmethod
	def _render_html(user: str, total_count: int, sections: list[dict]) -> str:
		try:
			config = frappe.get_single("Notification Window Settings").get_config()
			if config.batch_template:
				email_template = frappe.get_doc("Email Template", config.batch_template)
				context = {"user": user, "total_count": total_count, "sections": sections}
				return frappe.render_template(email_template.response_, context)

			return DigestBuilder._default_template(user, total_count, sections)

		except Exception as e:
			frappe.log_error(f"Error rendering HTML: {str(e)}", "Digest Builder")
			return DigestBuilder._default_template(user, total_count, sections)

	@staticmethod
	def _default_template(user: str, total_count: int, sections: list[dict]) -> str:
		user_name = frappe.db.get_value("User", user, "full_name") or user

		html = f"""
        <div style="font-family: monospace; max-width: 600px; margin: 0 auto; padding: 20px; background: #fafafa;">
            <h2 style="margin: 0 0 20px 0;">📋 {user_name}, you have new Assignments ({total_count})</h2>
        """

		for section in sections:
			html += f"""
            <div style="margin-bottom: 20px; padding: 15px; background: white; border: 1px solid #e5e7eb;">
                <strong>{section['doctype']}</strong> • {section['count']} item{'s' if section['count'] != 1 else ''}
                <ul style="margin: 10px 0 0 0; padding-left: 20px;">
            """

			for item in section["items"][:10]:
				html += f"""<li style="margin: 5px 0;"><a href="{item['url']}">{item['name']}</a></li>"""

			if section["count"] > 10:
				html += f"""<li style="color: #999;">+ {section['count'] - 10} more</li>"""

			html += f"""
                </ul>
                <a href="{section['report_url']}" style="font-size: 14px;">View all →</a>
            </div>
            """

		html += """
        </div>
        """

		return html
