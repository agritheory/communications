# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import json
import time

import frappe
from frappe import _
from frappe.model.document import Document

DEBUG_LOG_PATH = "/home/tyler/arrowwood/apps/.cursor/debug-c0c347.log"
DEBUG_SESSION_ID = "c0c347"


# #region agent log
def agent_debug_log(hypothesis_id, location, message, data=None):
	try:
		payload = {
			"sessionId": DEBUG_SESSION_ID,
			"hypothesisId": hypothesis_id,
			"location": location,
			"message": message,
			"data": data or {},
			"timestamp": int(time.time() * 1000),
		}
		with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as log_file:
			log_file.write(json.dumps(payload, default=str) + "\n")
	except Exception:
		pass


# #endregion


def strip_embedded_print_toolbar_html(html: str) -> str:
	"""Remove Frappe printview toolbar (Print / Get PDF) from HTML embedded on the website."""
	if not html or "action-banner" not in html:
		return html
	try:
		from bs4 import BeautifulSoup

		soup = BeautifulSoup(html, "html.parser")
		for node in soup.select(".action-banner"):
			node.decompose()
		return str(soup)
	except Exception:
		return html


def website_portal_signer_may_read(doc, user):
	"""Website User may read this doc on the portal when they are a listed signer (contact match)."""
	if not doc or not user or user == "Guest":
		return False
	user_type = frappe.db.get_value("User", user, "user_type")
	if user_type != "Website User":
		return False
	if doc.status not in ("Out for Signature", "Completed"):
		return False
	contact = frappe.db.get_value("Contact", {"user": user}, "name")
	if not contact:
		return False
	for row in doc.signers or []:
		if row.contact == contact:
			return True
	return False


class ElectronicSignature(Document):
	@property
	def document_html(self):
		"""HTML from the reference document's print view (no DB field)."""
		if not (self.reference_doctype and self.reference_name):
			return ""
		try:
			ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
			kwargs = {
				"print_format": self.print_format or None,
				"doc": ref_doc,
			}
			if frappe.db.has_column("Electronic Signature", "letter_head") and self.get("letter_head"):
				kwargs["letterhead"] = self.letter_head
			# Portal signers may read the Electronic Signature but not the referenced document.
			# frappe.get_print -> printview validates print permission on the reference doc under
			# the current session user, which would hide the agreement body for external signers.
			prev_ignore_print = bool(getattr(frappe.flags, "ignore_print_permissions", None))
			frappe.flags.ignore_print_permissions = True
			try:
				raw = frappe.get_print(self.reference_doctype, self.reference_name, **kwargs)
			finally:
				frappe.flags.ignore_print_permissions = prev_ignore_print
			return strip_embedded_print_toolbar_html(raw)
		except Exception:
			frappe.log_error(
				title="Electronic Signature document_html print render",
				message=frappe.get_traceback(),
			)
			return ""

	def has_permission(self, permtype="read", *, debug=False, user=None):
		# #region agent log
		user = user or frappe.session.user
		agent_debug_log(
			"H2_class_override",
			"electronic_signature.py:ElectronicSignature.has_permission",
			"entry",
			{
				"permtype": permtype,
				"user": user,
				"doc": getattr(self, "name", None),
				"status": getattr(self, "status", None),
				"ignore_permissions": bool(getattr(self.flags, "ignore_permissions", None)),
			},
		)
		# #endregion
		if getattr(self.flags, "ignore_permissions", None):
			return True
		if permtype == "read" and website_portal_signer_may_read(self, user):
			# #region agent log
			agent_debug_log(
				"H2_class_override",
				"electronic_signature.py:ElectronicSignature.has_permission",
				"granted_via_portal_signer",
				{"doc": self.name, "user": user},
			)
			# #endregion
			return True
		out = super().has_permission(permtype, debug=debug, user=user)
		# #region agent log
		agent_debug_log(
			"H2_class_override",
			"electronic_signature.py:ElectronicSignature.has_permission",
			"delegated_result",
			{"doc": self.name, "user": user, "permtype": permtype, "out": out},
		)
		# #endregion
		return out

	def validate(self):
		if self.reference_doctype and not self.reference_name:
			frappe.throw(_("Reference Name is required when Reference DocType is set."))
		if self.reference_name and not self.reference_doctype:
			frappe.throw(_("Reference DocType is required when Reference Name is set."))
		if self.print_format and not (self.reference_doctype and self.reference_name):
			frappe.throw(_("Set a reference document before choosing a Print Format."))
		if self.print_format and self.reference_doctype:
			pf_doctype = frappe.db.get_value("Print Format", self.print_format, "doc_type")
			if pf_doctype != self.reference_doctype:
				frappe.throw(_("Print Format must be for the same DocType as the reference."))
		if self.reference_doctype and self.reference_name:
			if not frappe.db.exists(self.reference_doctype, self.reference_name):
				frappe.throw(_("Referenced document does not exist."))
		if self.status == "Out for Signature":
			if not self.signers:
				frappe.throw(_("Add at least one signer before sending for signature."))
			for row in self.signers:
				if not row.email:
					frappe.throw(_("Each signer must have an email."))
		if self.status == "Completed":
			for row in self.signers or []:
				if not row.executed_at:
					frappe.throw(_("All signers must have executed before status can be Completed."))


def has_electronic_signature_permission(doc, user=None, ptype="read"):
	"""Hook: deny portal-ineligible Website Users only; never return True (that does not grant DocPerm read)."""
	user = user or frappe.session.user
	# #region agent log
	agent_debug_log(
		"H1_hook",
		"electronic_signature.py:has_electronic_signature_permission",
		"entry",
		{
			"ptype": ptype,
			"user": user,
			"doc": getattr(doc, "name", doc) if doc is not None else None,
			"doc_status": getattr(doc, "status", None) if doc is not None else None,
		},
	)
	# #endregion
	if not doc:
		return None
	if ptype != "read":
		return None
	user_type = frappe.db.get_value("User", user, "user_type")
	if user_type == "System User":
		# #region agent log
		agent_debug_log(
			"H1_hook",
			"electronic_signature.py:has_electronic_signature_permission",
			"system_user_defer",
			{},
		)
		# #endregion
		return None
	if user_type != "Website User":
		# #region agent log
		agent_debug_log(
			"H3_user_type",
			"electronic_signature.py:has_electronic_signature_permission",
			"not_website_user_false",
			{"user_type": user_type},
		)
		# #endregion
		return False
	if website_portal_signer_may_read(doc, user):
		# #region agent log
		agent_debug_log(
			"H1_hook",
			"electronic_signature.py:has_electronic_signature_permission",
			"signer_return_none",
			{"doc": doc.name},
		)
		# #endregion
		return None
	# #region agent log
	agent_debug_log(
		"H1_hook",
		"electronic_signature.py:has_electronic_signature_permission",
		"non_signer_false",
		{"doc": doc.name, "user": user},
	)
	# #endregion
	return False
