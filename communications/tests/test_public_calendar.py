# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import json
from datetime import datetime
from threading import Thread
from unittest.mock import patch

import frappe
import pytest
from frappe.utils import get_test_client

from communications.communications.ics import (
	escape_ics_param,
	escape_ics_text,
	generate_ics,
	generate_ics_attachment,
)
from communications.communications.notifications import (
	reminder_already_sent,
	generate_rsvp_token,
	get_host_and_guests,
	get_public_calendar_for_event,
	get_rsvp_url,
	notify_booking,
	notify_cancellation,
	notify_reschedule,
	verify_rsvp_token,
)
from communications.www.calendar.index import get_context as calendar_get_context
from communications.www.rsvp.index import find_participant_by_email
from communications.www.rsvp.index import get_context as rsvp_get_context
from communications.www.schedule.index import get_context as schedule_get_context

HOST_EMAIL = "dbenton@cfc.co"
GUEST_EMAIL = "arivers@cfc.co"
ADMIN_PASSWORD = "admin"
GUEST_PASSWORD = "Test@1234"

CALENDAR_ROUTE = "dbenton"

DOC_CALENDAR_HOST = HOST_EMAIL
DOC_CALENDAR_ROUTE_SUPPLIER_TASTINGS = "dbenton-supplier-tastings"
DOC_CALENDAR_ROUTE_HOST_SHARE = "dbenton-share-audit"
DOC_CALENDAR_ROUTE_INVALID_HOURS = "dbenton-invalid-working-hours"


wsgi_test_client = None
wsgi_test_site = None


def ensure_wsgi_test_client():
	global wsgi_test_client, wsgi_test_site
	if wsgi_test_client is None:
		import frappe.app as frappe_app_module

		wsgi_test_site = frappe.local.site
		frappe_app_module._site = wsgi_test_site
		frappe_app_module._sites_path = str(frappe.local.sites_path)
		wsgi_test_client = get_test_client()


class WsgiRequestThread(Thread):
	"""Run a single werkzeug test-client call in a thread for frappe.local isolation."""

	def __init__(self, fn, path, **kwargs):
		super().__init__(daemon=True)
		self.request_fn = fn
		self.request_path = path
		self.request_kwargs = kwargs
		self.response = None
		self.captured_exception = None

	def run(self):
		try:
			self.response = self.request_fn(self.request_path, **self.request_kwargs)
		except Exception as e:
			self.captured_exception = e

	def join(self, timeout=None):
		super().join(timeout=timeout)
		if self.captured_exception is not None:
			raise self.captured_exception


def wsgi_http_request(method, path, data=None):
	ensure_wsgi_test_client()
	kwargs = {"json": data} if data is not None else {}
	thread = WsgiRequestThread(getattr(wsgi_test_client, method), path, **kwargs)
	thread.start()
	thread.join()
	return thread.response


def login_wsgi_client(user, password):
	response = wsgi_http_request("post", "/api/method/login", {"usr": user, "pwd": password})
	assert response.status_code == 200, f"Login as {user!r} failed ({response.status_code})"


def api_message_from_response(response):
	return json.loads(response.data)["message"]


def upcoming_slot_string(days_ahead=7, hour=10):
	d = frappe.utils.add_days(frappe.utils.getdate(), days_ahead)
	return f"{d} {hour:02d}:00:00"


def get_fixture_booked_event():
	"""Look up the shared booked event created by before_test."""
	name = frappe.db.get_value(
		"Event", {"subject": "Test Appointment", "reference_docname": CALENDAR_ROUTE}, "name"
	)
	return frappe.get_doc("Event", name)


def make_fake_event(name="EVT-001", all_day=0, starts_on=None, ends_on=None):
	_d = frappe.utils.add_days(frappe.utils.getdate(), 7)
	_d_next = frappe.utils.add_days(frappe.utils.getdate(), 8)
	default_start = datetime(_d.year, _d.month, _d.day, 10, 0)
	default_end = (
		datetime(_d_next.year, _d_next.month, _d_next.day)
		if all_day
		else datetime(_d.year, _d.month, _d.day, 11, 0)
	)
	return frappe._dict(
		{
			"name": name,
			"subject": "Test Meeting",
			"description": None,
			"starts_on": starts_on if starts_on is not None else default_start,
			"ends_on": ends_on if ends_on is not None else default_end,
			"all_day": all_day,
			"location": None,
			"get": lambda key, default=None: None,
		}
	)


@pytest.mark.order(1)
def test_generate_ics_request_method():
	event = make_fake_event()
	ics = generate_ics(event, method="REQUEST")
	assert "BEGIN:VCALENDAR" in ics
	assert "METHOD:REQUEST" in ics
	assert "BEGIN:VEVENT" in ics
	assert f"UID:{event.name}@" in ics
	assert "STATUS:CONFIRMED" in ics
	assert "END:VEVENT" in ics
	assert "END:VCALENDAR" in ics


@pytest.mark.order(2)
def test_generate_ics_cancel_method():
	event = make_fake_event()
	ics = generate_ics(event, method="CANCEL")
	assert "METHOD:CANCEL" in ics
	assert "STATUS:CANCELLED" in ics


@pytest.mark.order(3)
def test_generate_ics_all_day_event():
	_d = frappe.utils.add_days(frappe.utils.getdate(), 7)
	_d_next = frappe.utils.add_days(frappe.utils.getdate(), 8)
	starts = datetime(_d.year, _d.month, _d.day)
	ends = datetime(_d_next.year, _d_next.month, _d_next.day)
	event = make_fake_event(all_day=1, starts_on=starts, ends_on=ends)
	ics = generate_ics(event, method="REQUEST")
	assert f"DTSTART;VALUE=DATE:{starts.strftime('%Y%m%d')}" in ics
	assert f"DTEND;VALUE=DATE:{ends.strftime('%Y%m%d')}" in ics
	assert "DTSTART:" not in ics.replace("DTSTART;VALUE=DATE:", "")


@pytest.mark.order(4)
def test_ics_escape_text():
	assert escape_ics_text("back\\slash") == "back\\\\slash"
	assert escape_ics_text("semi;colon") == "semi\\;colon"
	assert escape_ics_text("com,ma") == "com\\,ma"
	assert escape_ics_text("new\nline") == "new\\nline"
	assert escape_ics_text("cr\ronly") == "cr\\nonly"
	assert escape_ics_text("crlf\r\nend") == "crlf\\nend"


@pytest.mark.order(5)
def test_ics_escape_param_quotes_special_chars():
	# plain name — no quoting needed
	assert escape_ics_param("Jane Doe") == "Jane Doe"
	# colon triggers quoting
	result = escape_ics_param("Org: Dept")
	assert result.startswith('"') and result.endswith('"')
	# semicolon triggers quoting
	result = escape_ics_param("A;B")
	assert result.startswith('"') and result.endswith('"')
	# embedded double-quote is escaped inside the quoted string
	result = escape_ics_param('Say "hello"')
	assert '\\"' in result


@pytest.mark.order(6)
def test_generate_ics_attachment_dict():
	event = make_fake_event()
	attachment = generate_ics_attachment(event, method="REQUEST")
	assert attachment["fname"] == "invite.ics"
	assert "BEGIN:VCALENDAR" in attachment["fcontent"]
	assert attachment["content_type"] == "text/calendar; method=REQUEST"

	cancel_attachment = generate_ics_attachment(event, method="CANCEL")
	assert cancel_attachment["fname"] == "cancellation.ics"
	assert cancel_attachment["content_type"] == "text/calendar; method=CANCEL"


@pytest.mark.order(7)
def test_rsvp_token_is_deterministic():
	t1 = generate_rsvp_token("EVT-001", "user@example.com", "confirm")
	t2 = generate_rsvp_token("EVT-001", "user@example.com", "confirm")
	assert t1 == t2
	assert len(t1) == 32


@pytest.mark.order(8)
def test_rsvp_token_different_actions_differ():
	confirm = generate_rsvp_token("EVT-001", "user@example.com", "confirm")
	cancel = generate_rsvp_token("EVT-001", "user@example.com", "cancel")
	decline = generate_rsvp_token("EVT-001", "user@example.com", "decline")
	assert confirm != cancel
	assert confirm != decline
	assert cancel != decline


@pytest.mark.order(9)
def test_verify_rsvp_token_valid():
	token = generate_rsvp_token("EVT-001", "user@example.com", "confirm")
	assert verify_rsvp_token("EVT-001", "user@example.com", "confirm", token) is True


@pytest.mark.order(10)
def test_verify_rsvp_token_invalid():
	assert (
		verify_rsvp_token("EVT-001", "user@example.com", "confirm", "notavalidtoken123456789012345678")
		is False
	)


@pytest.mark.order(11)
def test_get_rsvp_url_contains_expected_params():
	url = get_rsvp_url("EVT-001", "user@example.com", "confirm")
	assert "event=EVT-001" in url
	assert "email=user@example.com" in url
	assert "action=confirm" in url
	assert "token=" in url


@pytest.mark.order(12)
def test_get_public_calendar_for_event():
	linked_event = frappe._dict(
		{
			"reference_doctype": "Public Calendar",
			"reference_docname": CALENDAR_ROUTE,
			"get": lambda key, default=None: getattr(
				frappe._dict({"reference_doctype": "Public Calendar", "reference_docname": CALENDAR_ROUTE}),
				key,
				default,
			),
		}
	)
	result = get_public_calendar_for_event(linked_event)
	assert result is not None
	assert result.name == CALENDAR_ROUTE

	unlinked_event = frappe._dict({"get": lambda key, default=None: None})
	assert get_public_calendar_for_event(unlinked_event) is None


@pytest.mark.order(13)
def test_get_host_and_guests_splits_correctly():
	calendar = frappe.get_doc("Public Calendar", CALENDAR_ROUTE)
	event = get_fixture_booked_event()

	host, guests = get_host_and_guests(event, calendar)

	assert host is not None
	assert host["email"] == HOST_EMAIL
	assert len(guests) == 1
	assert guests[0]["email"] == GUEST_EMAIL


@pytest.mark.order(14)
def test_reminder_already_sent_false_initially():
	event = get_fixture_booked_event()
	assert not reminder_already_sent(event.name)


@pytest.mark.order(15)
def test_reminder_already_sent_true_after_comment():
	event = get_fixture_booked_event()

	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Event",
			"reference_name": event.name,
			"content": "Reminder sent",
		}
	).insert(ignore_permissions=True)

	assert reminder_already_sent(event.name)

	frappe.db.delete("Comment", {"reference_doctype": "Event", "reference_name": event.name})


@pytest.mark.order(16)
@patch("frappe.sendmail")
def test_notify_booking_sends_to_host_and_guest(mock_sendmail):
	calendar = frappe.get_doc("Public Calendar", CALENDAR_ROUTE)
	event = get_fixture_booked_event()

	notify_booking(event, calendar)

	assert mock_sendmail.call_count == 2
	recipients = [call.kwargs["recipients"][0] for call in mock_sendmail.call_args_list]
	assert HOST_EMAIL in recipients
	assert GUEST_EMAIL in recipients


@pytest.mark.order(17)
@patch("frappe.sendmail")
def test_notify_cancellation_skips_when_flag_off(mock_sendmail):
	event = get_fixture_booked_event()
	cal_no_cancel = frappe._dict({"notify_on_cancellation": 0})

	notify_cancellation(event, cal_no_cancel, HOST_EMAIL)

	mock_sendmail.assert_not_called()


@pytest.mark.order(18)
@patch("frappe.sendmail")
def test_notify_cancellation_skips_canceller(mock_sendmail):
	calendar = frappe.get_doc("Public Calendar", CALENDAR_ROUTE)
	event = get_fixture_booked_event()

	notify_cancellation(event, calendar, HOST_EMAIL)

	# Host cancelled — only guest should be notified
	assert mock_sendmail.call_count == 1
	assert mock_sendmail.call_args.kwargs["recipients"][0] == GUEST_EMAIL


@pytest.mark.order(19)
@patch("frappe.sendmail")
def test_notify_reschedule_skips_rescheduler(mock_sendmail):
	calendar = frappe.get_doc("Public Calendar", CALENDAR_ROUTE)
	event = get_fixture_booked_event()

	notify_reschedule(event, calendar, GUEST_EMAIL)

	# Guest rescheduled — only host should be notified
	assert mock_sendmail.call_count == 1
	assert mock_sendmail.call_args.kwargs["recipients"][0] == HOST_EMAIL


@pytest.mark.order(20)
@patch("frappe.sendmail")
def test_notify_reschedule_from_host_notifies_guests(mock_sendmail):
	calendar = frappe.get_doc("Public Calendar", CALENDAR_ROUTE)
	event = get_fixture_booked_event()

	notify_reschedule(event, calendar, HOST_EMAIL)

	# Host rescheduled — only guest should be notified
	assert mock_sendmail.call_count == 1
	assert mock_sendmail.call_args.kwargs["recipients"][0] == GUEST_EMAIL


@pytest.mark.order(21)
def test_book_appointment_creates_event():
	with patch("frappe.sendmail"):
		login_wsgi_client(GUEST_EMAIL, GUEST_PASSWORD)
		response = wsgi_http_request(
			"post",
			"/api/method/communications.www.schedule.index.book_appointment",
			{
				"public_calendar": CALENDAR_ROUTE,
				"starts_on": upcoming_slot_string(days_ahead=14, hour=14),
				"ends_on": upcoming_slot_string(days_ahead=14, hour=15),
				"subject": "Test Booking",
			},
		)
		login_wsgi_client("Administrator", ADMIN_PASSWORD)

		assert response.status_code == 200
		event_name = api_message_from_response(response)
		assert event_name  # API returned the new event's name

		# Verify and clean up via the HTTP layer — the main thread's DB connection
		# runs under MySQL REPEATABLE READ and cannot see rows committed by the HTTP
		# thread, so we use a fresh request (new connection) for both checks.
		fetch = wsgi_http_request("get", f"/api/resource/Event/{event_name}")
		assert fetch.status_code == 200
		event_data = json.loads(fetch.data)["data"]
		assert event_data["reference_doctype"] == "Public Calendar"
		assert event_data["reference_docname"] == CALENDAR_ROUTE
		participant_users = [
			p["reference_docname"]
			for p in event_data.get("event_participants", [])
			if p["reference_doctype"] == "User"
		]
		assert HOST_EMAIL in participant_users
		assert GUEST_EMAIL in participant_users

		cleanup = wsgi_http_request("delete", f"/api/resource/Event/{event_name}")
		assert (
			cleanup.status_code == 202
		), f"Event cleanup DELETE failed: {cleanup.status_code} {cleanup.get_data(as_text=True)[:800]}"


@pytest.mark.order(22)
def test_book_appointment_links_task_when_reference_provided():
	if not frappe.db.has_column("Task", "portal_scheduled_event"):
		pytest.skip("Task.portal_scheduled_event not installed on this site")

	frappe.set_user("Administrator")
	projects = frappe.get_all(
		"Project", filters={"status": ["!=", "Cancelled"]}, limit=1, pluck="name"
	)
	if not projects:
		pytest.skip("No project for Task fixture")
	project = projects[0]

	task = frappe.get_doc(
		{
			"doctype": "Task",
			"subject": "Portal booking reference test",
			"project": project,
			"status": "Open",
		}
	)
	task.insert(ignore_permissions=True)
	task_name = task.name

	if not frappe.db.exists("Project User", {"parent": project, "user": GUEST_EMAIL}):
		frappe.get_doc(
			{
				"doctype": "Project User",
				"parent": project,
				"parenttype": "Project",
				"user": GUEST_EMAIL,
			}
		).insert(ignore_permissions=True)

	frappe.db.commit()

	with patch("frappe.sendmail"):
		login_wsgi_client(GUEST_EMAIL, GUEST_PASSWORD)
		response = wsgi_http_request(
			"post",
			"/api/method/communications.www.schedule.index.book_appointment",
			{
				"public_calendar": CALENDAR_ROUTE,
				"starts_on": upcoming_slot_string(days_ahead=21, hour=15),
				"ends_on": upcoming_slot_string(days_ahead=21, hour=16),
				"subject": "Booking with Task ref",
				"reference_doctype": "Task",
				"reference_docname": task_name,
			},
		)
	login_wsgi_client("Administrator", ADMIN_PASSWORD)

	assert response.status_code == 200
	event_name = api_message_from_response(response)
	assert event_name

	fetch = wsgi_http_request("get", f"/api/resource/Task/{task_name}")
	assert fetch.status_code == 200
	task_data = json.loads(fetch.data)["data"]
	assert task_data.get("portal_scheduled_event") == event_name

	cleanup_ev = wsgi_http_request("delete", f"/api/resource/Event/{event_name}")
	assert cleanup_ev.status_code == 202
	frappe.delete_doc("Task", task_name, force=True, ignore_permissions=True)
	frappe.db.commit()


@pytest.mark.order(23)
def test_book_appointment_skips_task_link_when_user_has_no_project_access():
	if not frappe.db.has_column("Task", "portal_scheduled_event"):
		pytest.skip("Task.portal_scheduled_event not installed on this site")

	frappe.set_user("Administrator")
	iso = frappe.new_doc("Project")
	iso.project_name = "Isolated booking ref test"
	iso.status = "Open"
	iso.insert(ignore_permissions=True)

	task = frappe.get_doc(
		{
			"doctype": "Task",
			"subject": "Inaccessible task for booking ref",
			"project": iso.name,
			"status": "Open",
		}
	)
	task.insert(ignore_permissions=True)
	task_name = task.name
	frappe.db.commit()

	with patch("frappe.sendmail"):
		login_wsgi_client(GUEST_EMAIL, GUEST_PASSWORD)
		response = wsgi_http_request(
			"post",
			"/api/method/communications.www.schedule.index.book_appointment",
			{
				"public_calendar": CALENDAR_ROUTE,
				"starts_on": upcoming_slot_string(days_ahead=22, hour=11),
				"ends_on": upcoming_slot_string(days_ahead=22, hour=12),
				"subject": "Booking inaccessible task ref",
				"reference_doctype": "Task",
				"reference_docname": task_name,
			},
		)
	login_wsgi_client("Administrator", ADMIN_PASSWORD)

	assert response.status_code == 200
	event_name = api_message_from_response(response)

	fetch = wsgi_http_request("get", f"/api/resource/Task/{task_name}")
	assert fetch.status_code == 200
	task_data = json.loads(fetch.data)["data"]
	assert not task_data.get("portal_scheduled_event")

	cleanup_ev = wsgi_http_request("delete", f"/api/resource/Event/{event_name}")
	assert cleanup_ev.status_code == 202
	frappe.delete_doc("Task", task_name, force=True, ignore_permissions=True)
	frappe.delete_doc("Project", iso.name, force=True, ignore_permissions=True)
	frappe.db.commit()


@pytest.mark.order(24)
def test_get_calendar_events_returns_booked_event():
	start = f"{frappe.utils.getdate()} 00:00:00"
	end = f"{frappe.utils.add_days(frappe.utils.getdate(), 14)} 23:59:59"

	response = wsgi_http_request(
		"post",
		"/api/method/communications.www.calendar.index.get_events",
		{"start": start, "end": end, "public_calendar": CALENDAR_ROUTE},
	)

	assert response.status_code == 200
	events = api_message_from_response(response)
	assert isinstance(events, list)
	assert len(events) >= 1
	assert all(e["calendar"] == CALENDAR_ROUTE for e in events)


@pytest.mark.order(25)
def test_get_calendar_events_without_filter():
	start = f"{frappe.utils.getdate()} 00:00:00"
	end = f"{frappe.utils.add_days(frappe.utils.getdate(), 14)} 23:59:59"

	response = wsgi_http_request(
		"post",
		"/api/method/communications.www.calendar.index.get_events",
		{"start": start, "end": end},
	)

	assert response.status_code == 200
	events = api_message_from_response(response)
	assert isinstance(events, list)
	assert any(e["calendar"] == CALENDAR_ROUTE for e in events)


@pytest.mark.order(26)
def test_get_schedule_events_shows_booked_slot():
	start = f"{frappe.utils.getdate()} 00:00:00"
	end = f"{frappe.utils.add_days(frappe.utils.getdate(), 14)} 23:59:59"

	response = wsgi_http_request(
		"post",
		"/api/method/communications.www.schedule.index.get_events",
		{"start": start, "end": end, "public_calendar": CALENDAR_ROUTE},
	)

	assert response.status_code == 200
	events = api_message_from_response(response)
	assert isinstance(events, list)
	assert len(events) >= 1


@pytest.mark.order(27)
def test_rsvp_missing_params_returns_error():
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict()
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is not None
		assert context.result is None
	finally:
		frappe.local.form_dict = _saved


@pytest.mark.order(28)
def test_rsvp_invalid_token_returns_error():
	event = get_fixture_booked_event()
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(
		{
			"event": event.name,
			"email": GUEST_EMAIL,
			"action": "confirm",
			"token": "notavalidtoken123456789012345678",
		}
	)
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is not None
		assert context.result is None
	finally:
		frappe.local.form_dict = _saved


@pytest.mark.order(29)
@patch("frappe.sendmail")
def test_rsvp_confirm_via_context(_):
	event = get_fixture_booked_event()
	token = generate_rsvp_token(event.name, GUEST_EMAIL, "confirm")
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(
		{
			"event": event.name,
			"email": GUEST_EMAIL,
			"action": "confirm",
			"token": token,
		}
	)
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is None
		assert context.result["action"] == "confirm"
	finally:
		frappe.local.form_dict = _saved

	event.reload()
	updated = find_participant_by_email(event, GUEST_EMAIL)
	assert updated.rsvp == "Accepted"


@pytest.mark.order(30)
@patch("frappe.sendmail")
def test_rsvp_cancel_via_context(_):
	event = get_fixture_booked_event()
	token = generate_rsvp_token(event.name, GUEST_EMAIL, "cancel")
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(
		{
			"event": event.name,
			"email": GUEST_EMAIL,
			"action": "cancel",
			"token": token,
		}
	)
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is None
		assert context.result["action"] == "cancel"
	finally:
		frappe.local.form_dict = _saved

	event.reload()
	assert event.status == "Cancelled"
	updated = find_participant_by_email(event, GUEST_EMAIL)
	assert updated.rsvp == "Cancelled"


@pytest.mark.order(31)
def test_calendar_page_context_with_route():
	saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict({"name": CALENDAR_ROUTE})
	try:
		context = frappe._dict()
		calendar_get_context(context)
		assert context.selected_calendar == CALENDAR_ROUTE
		assert context.public_calendars
	finally:
		frappe.local.form_dict = saved


@pytest.mark.order(32)
def test_calendar_page_context_no_route():
	saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict()
	try:
		context = frappe._dict()
		calendar_get_context(context)
		assert context.selected_calendar is None
		assert context.public_calendars
	finally:
		frappe.local.form_dict = saved


@pytest.mark.order(33)
def test_schedule_page_context_with_route():
	saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict({"name": CALENDAR_ROUTE})
	try:
		context = frappe._dict()
		schedule_get_context(context)
		assert context.calendar is not None
		assert context.calendar.route == CALENDAR_ROUTE
	finally:
		frappe.local.form_dict = saved


@pytest.mark.order(34)
def test_schedule_page_context_no_route():
	saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict()
	try:
		context = frappe._dict()
		schedule_get_context(context)
		assert context.calendar is None
		assert context.schedulable_calendars
	finally:
		frappe.local.form_dict = saved


@pytest.mark.order(35)
def test_rsvp_invalid_action_returns_error():
	event = get_fixture_booked_event()
	token = generate_rsvp_token(event.name, GUEST_EMAIL, "confirm")
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(
		{"event": event.name, "email": GUEST_EMAIL, "action": "teleport", "token": token}
	)
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is not None
		assert context.result is None
	finally:
		frappe.local.form_dict = _saved


@pytest.mark.order(36)
def test_rsvp_nonexistent_event_returns_error():
	token = generate_rsvp_token("NO-SUCH-EVENT", GUEST_EMAIL, "confirm")
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(
		{"event": "NO-SUCH-EVENT", "email": GUEST_EMAIL, "action": "confirm", "token": token}
	)
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is not None
		assert context.result is None
	finally:
		frappe.local.form_dict = _saved


@pytest.mark.order(37)
def test_rsvp_non_participant_returns_error():
	event = get_fixture_booked_event()
	non_participant = "mmckay@cfc.co"
	token = generate_rsvp_token(event.name, non_participant, "confirm")
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(
		{"event": event.name, "email": non_participant, "action": "confirm", "token": token}
	)
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is not None
		assert context.result is None
	finally:
		frappe.local.form_dict = _saved


@pytest.mark.order(38)
@patch("frappe.sendmail")
def test_rsvp_decline_via_context(_):
	event = get_fixture_booked_event()
	token = generate_rsvp_token(event.name, GUEST_EMAIL, "decline")
	_saved = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(
		{"event": event.name, "email": GUEST_EMAIL, "action": "decline", "token": token}
	)
	try:
		context = frappe._dict()
		rsvp_get_context(context)
		assert context.error is None
		assert context.result["action"] == "decline"
	finally:
		frappe.local.form_dict = _saved

	event.reload()
	updated = find_participant_by_email(event, GUEST_EMAIL)
	assert updated.rsvp == "Declined"


@pytest.mark.order(40)
def test_public_calendar_insert_persists_title_user_and_route():
	"""Operations host gets a second public calendar row autonamed from its route."""
	if frappe.db.exists("Public Calendar", DOC_CALENDAR_ROUTE_SUPPLIER_TASTINGS):
		frappe.delete_doc(
			"Public Calendar", DOC_CALENDAR_ROUTE_SUPPLIER_TASTINGS, force=1, ignore_permissions=True
		)

	calendar = frappe.get_doc(
		{
			"doctype": "Public Calendar",
			"title": "Darnell Benton — Supplier tastings",
			"user": DOC_CALENDAR_HOST,
			"route": DOC_CALENDAR_ROUTE_SUPPLIER_TASTINGS,
			"is_public": 1,
			"enabled": 1,
		}
	)
	calendar.insert(ignore_permissions=True)

	assert calendar.name == DOC_CALENDAR_ROUTE_SUPPLIER_TASTINGS
	assert calendar.title == "Darnell Benton — Supplier tastings"
	assert calendar.user == DOC_CALENDAR_HOST

	frappe.delete_doc("Public Calendar", calendar.name, force=1, ignore_permissions=True)


@pytest.mark.order(45)
def test_public_calendar_rejects_overlapping_working_hours():
	"""Overlapping Monday blocks on the same day fail validation before insert."""
	calendar = frappe.get_doc(
		{
			"doctype": "Public Calendar",
			"title": "Darnell Benton — Bad hours",
			"user": DOC_CALENDAR_HOST,
			"route": DOC_CALENDAR_ROUTE_INVALID_HOURS,
			"working_hours": json.dumps(
				{
					"monday": [
						{"start": "09:00", "end": "12:00"},
						{"start": "11:00", "end": "14:00"},
					]
				}
			),
		}
	)

	with pytest.raises(frappe.ValidationError, match="overlap"):
		calendar.insert(ignore_permissions=True)


@pytest.mark.order(50)
def test_public_calendar_shares_with_host_on_insert():
	"""New calendar is DocShared to the host user for read/write."""
	if frappe.db.exists("Public Calendar", DOC_CALENDAR_ROUTE_HOST_SHARE):
		frappe.delete_doc(
			"Public Calendar", DOC_CALENDAR_ROUTE_HOST_SHARE, force=1, ignore_permissions=True
		)

	calendar = frappe.get_doc(
		{
			"doctype": "Public Calendar",
			"title": "Darnell Benton — Share check",
			"user": DOC_CALENDAR_HOST,
			"route": DOC_CALENDAR_ROUTE_HOST_SHARE,
		}
	)
	calendar.insert(ignore_permissions=True)

	assert frappe.db.exists(
		"DocShare",
		{
			"share_doctype": "Public Calendar",
			"share_name": calendar.name,
			"user": DOC_CALENDAR_HOST,
		},
	)

	frappe.delete_doc("Public Calendar", calendar.name, force=1, ignore_permissions=True)
