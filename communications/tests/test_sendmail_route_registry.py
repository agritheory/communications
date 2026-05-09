# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

"""Sendmail routing keys and hydrate / validation behavior tests.

Designed integration scenarios (Notification documents with ``sendmail_route_key``
after migrate):

1. Frappe assignment: email from Notification Log uses ``send_notification_email`` calling
   ``sendmail``. Prefer ``generate_route_key_for_callable(send_notification_email)`` for matches.
   Separate Notification rows differentiate by DocType/Event (e.g., ToDo) while sharing keys.

2. Frappe tagging / mentions: ``notify_mentions`` enqueues alerts; EMAIL uses the digest path
   ``send_notification_email`` above. Optionally record ``notify_mentions`` as an extra key.

3. ERPNext project users: ``Project.send_welcome_email`` (requires **erpnext** on the bench; test
   errors if the package is not importable).

Import hydrate: invalid entries in ``communications_sendmail_routes`` are skipped (no throw).

``CommunicationsNotification.validate`` uses the same rules as ``validate_route_key_or_throw`` when
the field exists on the serialized doc (definition: ``communications/.../custom/notification.json``).
"""


from typing import Any

import frappe
import pytest

from communications.communications.overrides import sendmail as sendmail_mod
from communications.communications.overrides.sendmail import hydrate
from communications.communications.overrides.sendmail_routing import (
	generate_route_key_for_callable,
	validate_route_key_or_throw,
	warm_reference_call_site_keys,
)


def test_generated_key_send_notification_email():
	from frappe.desk.doctype.notification_log.notification_log import send_notification_email

	k = generate_route_key_for_callable(send_notification_email)
	assert k.endswith("|Q:send_notification_email")
	validate_route_key_or_throw(k)


def test_generated_key_notify_mentions():
	from frappe.desk.notifications import notify_mentions

	k = generate_route_key_for_callable(notify_mentions)
	assert "|Q:notify_mentions" in k
	validate_route_key_or_throw(k)


def test_generated_key_project_send_welcome_email():
	from erpnext.projects.doctype.project.project import Project

	k = generate_route_key_for_callable(Project.send_welcome_email)
	assert "|Q:Project.send_welcome_email" in k
	validate_route_key_or_throw(k)


def test_validate_route_throws_bad_prefix():
	with pytest.raises(frappe.ValidationError):
		validate_route_key_or_throw("no-prefix")


def test_validate_route_accepts_known_m_format():
	validate_route_key_or_throw(
		"M:frappe.desk.notifications|Q:notify_mentions",
	)


def test_hydrate_skips_bad_keys(monkeymodule):
	monkeymodule.setattr(
		frappe,
		"get_site_config",
		lambda **kwargs: {"communications_sendmail_routes": {"oops": {}, "T:approved": {}}},
	)

	received: list[tuple[Any, ...]] = []

	def track_put(sk: str, notify: bool, source: str | None = None):
		received.append((sk, notify, source))

	monkeymodule.setattr(sendmail_mod, "route_put", track_put)
	hydrate()
	assert received == [("T:approved", True, "site_config")]


def test_warm_reference_call_site_imports():
	warm_reference_call_site_keys()
