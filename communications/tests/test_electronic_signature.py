# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import frappe
import pytest

from communications.communications.install import create_electronic_signature_email_template
from communications.communications.doctype.electronic_signature.electronic_signature import (
	has_electronic_signature_permission,
)
from communications.www.electronic_signature import add_signature


@pytest.fixture
def signature_email_template():
	create_electronic_signature_email_template()


def make_website_signer_user(email, contact_first="Signer", contact_last="Test"):
	if frappe.db.exists("User", email):
		return frappe.get_doc("User", email)
	user = frappe.new_doc("User")
	user.email = email
	user.first_name = contact_first
	user.last_name = contact_last
	user.enabled = 1
	user.send_welcome_email = 0
	user.user_type = "Website User"
	user.append("roles", {"role": "Customer"})
	user.save()

	contact = frappe.new_doc("Contact")
	contact.first_name = contact_first
	contact.last_name = contact_last
	contact.append("email_ids", {"email_id": email, "is_primary": 1})
	contact.user = user.name
	contact.insert(ignore_permissions=True)

	return user


def make_electronic_signature_with_signers(signers_status="Out for Signature"):
	suffix = frappe.generate_hash(length=8)
	email = f"esign_test_{suffix}@example.com"
	user = make_website_signer_user(email)
	contact_name = frappe.db.get_value("Contact", {"user": email}, "name")

	es = frappe.new_doc("Electronic Signature")
	es.title = "Test Agreement"
	es.naming_series = "ESIG-.YYYY.-"
	es.status = signers_status
	es.introduction = "<p>Please read and sign.</p>"
	es.append(
		"signers",
		{
			"contact": contact_name,
			"email": email,
		},
	)
	es.insert(ignore_permissions=True)
	return es, email, contact_name


def test_add_signature_completes_and_sets_status(signature_email_template):
	es, email, contact_name = make_electronic_signature_with_signers()
	frappe.set_user(email)
	assert es.has_permission("read", user=email) is True

	payload = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
	out = add_signature(es.name, payload)
	assert out.get("success") is True

	es.reload()
	assert es.status == "Completed"
	assert es.signers[0].executed_at
	assert es.signers[0].signature

	frappe.set_user("Administrator")


def test_add_signature_rejects_duplicate(signature_email_template):
	es, email, contact_name = make_electronic_signature_with_signers()
	frappe.set_user(email)
	payload = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
	add_signature(es.name, payload)
	with pytest.raises(frappe.ValidationError):
		add_signature(es.name, payload)
	frappe.set_user("Administrator")


def test_add_signature_rejects_wrong_user(signature_email_template):
	es, email, contact_name = make_electronic_signature_with_signers()
	frappe.set_user("Administrator")
	other_email = f"other_esign_{frappe.generate_hash(length=6)}@example.com"
	other = make_website_signer_user(other_email)
	frappe.set_user(other.email)
	with pytest.raises(frappe.ValidationError):
		add_signature(
			es.name,
			"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
		)
	frappe.set_user("Administrator")


def test_has_permission_denies_non_signer_customer(signature_email_template):
	es, email, contact_name = make_electronic_signature_with_signers()
	other_email = f"stranger_esign_{frappe.generate_hash(length=6)}@example.com"
	other = make_website_signer_user(other_email)
	assert has_electronic_signature_permission(es, user=other.name, ptype="read") is False


def test_fetch_signature_invitation_email(signature_email_template):
	es, email, contact_name = make_electronic_signature_with_signers("Draft")
	frappe.set_user("Administrator")
	from communications.communications.signatures import fetch_signature_invitation_email

	out = fetch_signature_invitation_email(es.as_dict(), email)
	assert "subject" in out
	assert email in (out.get("recipients") or "")


def test_two_signers_then_completed(signature_email_template):
	frappe.set_user("Administrator")
	email_a = f"esign_a_{frappe.generate_hash(length=6)}@example.com"
	email_b = f"esign_b_{frappe.generate_hash(length=6)}@example.com"
	make_website_signer_user(email_a, "Alice", "One")
	make_website_signer_user(email_b, "Bob", "Two")
	contact_a = frappe.db.get_value("Contact", {"user": email_a}, "name")
	contact_b = frappe.db.get_value("Contact", {"user": email_b}, "name")

	es = frappe.new_doc("Electronic Signature")
	es.title = "Dual sign"
	es.naming_series = "ESIG-.YYYY.-"
	es.status = "Out for Signature"
	es.append("signers", {"contact": contact_a, "email": email_a})
	es.append("signers", {"contact": contact_b, "email": email_b})
	es.insert(ignore_permissions=True)

	frappe.set_user(email_a)
	add_signature(
		es.name,
		"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
	)
	es.reload()
	assert es.status == "Out for Signature"

	frappe.set_user(email_b)
	add_signature(
		es.name,
		"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
	)
	es.reload()
	assert es.status == "Completed"
	frappe.set_user("Administrator")
