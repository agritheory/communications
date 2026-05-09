# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

from __future__ import annotations

import functools
import inspect
from pathlib import Path
from types import CodeType
from typing import Any
from collections.abc import Callable

import frappe
from frappe import _

from communications.communications.overrides.sendmail_routing import (
	communications_sendmail_log,
	validate_route_key_lenient_skip,
	warm_reference_call_site_keys,
)

original_sendmail: Callable[..., Any] | None = None
sendmail_dispatch_code: CodeType | None = None
ROUTE_HASH = "communications_sendmail_routes"
NOTIFICATION_ROUTE_KEYS_VALUE = "communications_sendmail_notification_route_keys"


def routing_caller_frames() -> list[inspect.FrameInfo]:
	stack = inspect.stack()[1:]
	i = 0
	while i < len(stack):
		co = stack[i].frame.f_code
		if co is iterate_keys.__code__ or (
			sendmail_dispatch_code is not None and co is sendmail_dispatch_code
		):
			i += 1
			continue
		break
	return stack[i:]


def hydrate():
	if not frappe.cache:
		return
	cfg = frappe.get_site_config(
		sites_path=getattr(frappe.local, "sites_path", None),
		site_path=getattr(frappe.local, "site_path", None),
	)
	m = cfg.get("communications_sendmail_routes") if cfg else None
	if not isinstance(m, dict):
		return
	log = communications_sendmail_log()
	for ks, val in m.items():
		sk = ks if isinstance(ks, str) else str(ks)
		if not validate_route_key_lenient_skip(sk):
			log.warning(
				"communications_sendmail_routes skips invalid route key %r",
				sk[:200],
			)
			continue
		route_put(
			sk,
			isinstance(val, dict) and bool(val.get("notify_only", True)),
			source="site_config",
		)


def reconcile_notification_routes():
	if not getattr(frappe.local, "db", None):
		return
	if not frappe.db.has_column("Notification", "sendmail_route_key"):
		return

	log = communications_sendmail_log()
	keys = (
		frappe.db.sql(
			"""
		SELECT TRIM(sendmail_route_key)
		FROM tabNotification
		WHERE COALESCE(enabled, 0)=1
		  AND TRIM(IFNULL(sendmail_route_key, ''))!=''
		""",
			pluck=True,
		)
		or []
	)
	ok: set[str] = set()
	for sk in keys:
		t = (sk or "").strip()
		if not t:
			continue
		if validate_route_key_lenient_skip(t):
			ok.add(t)
		else:
			log.warning("notification sendmail_route_key invalid for enabled Notification: %r", t[:200])
	prev = frappe.cache.get_value(NOTIFICATION_ROUTE_KEYS_VALUE, shared=True) or []
	prev_set = set(prev) if isinstance(prev, list) else set()
	for sk in prev_set - ok:
		meta = frappe.cache.hget(ROUTE_HASH, sk, shared=True)
		payload = frappe._dict(meta if isinstance(meta, dict) else {})
		if payload.get("source") == "notification":
			route_del(sk)
	for sk in ok:
		route_put(sk, True, source="notification")
	frappe.cache.set_value(NOTIFICATION_ROUTE_KEYS_VALUE, list(ok), shared=True)


def bootstrap():
	global original_sendmail, sendmail_dispatch_code
	fn = frappe.sendmail
	if getattr(fn, "__communications_ov__", False):
		return
	original_sendmail = fn

	@functools.wraps(fn)
	def dispatch(*args, **kwargs):
		sig = inspect.signature(fn)
		try:
			bound = sig.bind_partial(*args, **kwargs)
			bound.apply_defaults()
		except TypeError:
			return original_sendmail(*args, **kwargs)
		conf = frappe._dict(bound.arguments)
		recipients = conf.get("recipients")
		for k in iterate_keys():
			val = frappe.cache.hget(ROUTE_HASH, k, shared=True)
			if isinstance(val, dict) and val.get("notify_only"):
				return enqueue_nl(recipients or [], conf)
		for k in iterate_tpl(conf):
			val = frappe.cache.hget(ROUTE_HASH, k, shared=True)
			if isinstance(val, dict) and val.get("notify_only"):
				return enqueue_nl(recipients or [], conf)
		return original_sendmail(*args, **kwargs)

	setattr(dispatch, "__communications_ov__", True)
	sendmail_dispatch_code = dispatch.__code__
	frappe.sendmail = dispatch
	hydrate()
	reconcile_notification_routes()
	warm_reference_call_site_keys()


def iterate_keys():
	seen: set[str] = set()
	for fr in routing_caller_frames():
		fm = fr.frame
		mod = fm.f_globals.get("__name__") or ""
		co = fm.f_code
		qual = getattr(co, "co_qualname", co.co_name)
		ln = fr.lineno or 0
		dot = dotted_from_file(getattr(fr, "filename", "") or "")
		for kk in (f"M:{mod}|Q:{qual}", f"M:{mod}|Q:{qual}|L:{ln}"):
			if kk not in seen:
				seen.add(kk)
				yield kk
		if dot:
			for kk in (f"P:{dot}|Q:{qual}", f"P:{dot}|Q:{qual}|L:{ln}"):
				if kk not in seen:
					seen.add(kk)
					yield kk


def dotted_from_file(fs: str) -> str | None:
	try:
		p = Path(fs).resolve()
	except OSError:
		return None
	for ax in anchors():
		try:
			rel = p.relative_to(ax.resolve())
			return ".".join(rel.with_suffix("").parts)
		except ValueError:
			continue
	return None


def anchors() -> list[Path]:
	o: list[Path] = []
	try:
		import frappe as _m

		o.append(Path(_m.__file__).resolve().parents[1])
	except Exception:
		pass
	o.append(Path(__file__).resolve().parents[4])
	return o


def iterate_tpl(conf: frappe._dict):
	t = conf.get("template")
	if t:
		yield f"T:{t}"
	s = conf.get("subject")
	if s and isinstance(s, str):
		yield f"S:{s[:400]}"


def enqueue_nl(recipients: Any, conf: frappe._dict):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	if isinstance(recipients, str):
		recipients = [x.strip() for x in recipients.split(",")] if recipients else []
	recipients = recipients or []
	subject = conf.get("subject") or _("No Subject")
	message = conf.get("message") or conf.get("content") or ""
	doc = frappe._dict(
		type="Alert",
		document_type=conf.get("reference_doctype") or conf.get("doctype"),
		document_name=conf.get("reference_name") or conf.get("name"),
		subject=subject,
		from_user=(getattr(frappe.session, "user", None) if getattr(frappe, "session", None) else None),
		email_content=message,
	)
	enqueue_create_notification(recipients, doc)
	return None


def on_site_ready():
	"""Called via before_request hook to warm caches once per process lifetime."""
	ready_key = "communications_sendmail_bootstrap_done"
	if frappe.cache.get_value(ready_key, shared=True):
		return
	hydrate()
	reconcile_notification_routes()
	warm_reference_call_site_keys()
	frappe.cache.set_value(ready_key, True, shared=True, expires_in_sec=3600)


def route_put(k: str, notify_only: bool, source: str | None = None):
	d = frappe._dict(notify_only=notify_only)
	if source:
		d.source = source
	frappe.cache.hset(ROUTE_HASH, str(k), d, shared=True)


route_set = route_put


def route_del(k: str):
	frappe.cache.hdel(ROUTE_HASH, str(k), shared=True)
