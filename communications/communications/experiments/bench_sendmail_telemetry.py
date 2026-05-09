# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt
"""
Bench console: monkey-patch frappe.sendmail to NDJSON telemetry (discovery).

Usage (bench console):
    import frappe
    from communications.communications.experiments import bench_sendmail_telemetry as t
    t.install_sendmail_probe()
    t.trigger_demo_sendmail()   # exercises sendmail from *this* module (no UI)
    t.uninstall_sendmail_probe()

Each sendmail prints semantic call sites to the console and appends NDJSON lines to the
log path shown on install. For real Frappe call sites (notification_log, Notification, …)
use the UI or other flows after installing the probe.

Do not rely on monkey-patching in production; REPL/experiments only.
"""

from __future__ import annotations

import functools
import inspect
import json
import time
from pathlib import Path
from typing import Any
from collections.abc import Callable

# #region agent log
SESSION_ID = "0c3f38"
DEBUG_LOG_PATH = "/home/tyler/redwood/apps/.cursor/debug-0c3f38.log"
original_sendmail: Callable[..., Any] | None = None


def write_ndjson(payload: dict) -> None:
	try:
		with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
			f.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")
	except Exception:
		pass


def dotted_path_prefix_from_file(fq_file: str) -> str | None:
	"""Dotted path under ``apps/<app>/…`` matching sendmail_callsites_ast ``package_prefix``."""

	try:
		fq_path = Path(fq_file).resolve()
	except OSError:
		return None

	anchors: list[Path] = []
	try:
		import frappe

		# Must match AST: analyze(..., package_root=<frappe app parent>), i.e. .../apps/frappe
		anchors.append(Path(frappe.__file__).resolve().parents[1])
	except Exception:
		pass

	here = Path(__file__).resolve()
	anchors.append(here.parents[3])
	seen: set[str] = set()
	for apex in anchors:
		key = str(apex.resolve())
		if key in seen:
			continue
		seen.add(key)
		try:
			rel = fq_path.relative_to(apex.resolve())
			return ".".join(rel.with_suffix("").parts)
		except ValueError:
			continue
	return None


def registry_keys_for_callsite(row: dict) -> dict[str, str | None]:
	"""Stable keys for hashtable overrides (printed + NDJSON).

	``path_scope_key_ast_aligned`` matches AST ``stable_key`` when scopes align
	(one sendmail per function body); use ``@N`` in registry if you mimic AST ordinals.

	"""

	mod = row.get("module") or ""
	qual = row.get("code_qual") or row.get("name") or ""

	module_scope_key = f"{mod}::{qual}"

	dotted = dotted_path_prefix_from_file(row.get("fq_file", ""))

	path_scope_key_ast_aligned = f"{dotted}::{qual}" if dotted else None

	return {
		"module_scope_key": module_scope_key,
		"path_scope_key_ast_aligned": path_scope_key_ast_aligned,
	}


def stack_frames_for_hypothesis(limit: int = 10) -> list[dict]:
	"""Frames from the first *semantic* caller of frappe.sendmail upward.

	inspect.stack() from inside this helper:
	  [0] = this function
	  [1] = probe_wrapper (the monkey-patch wrapper)
	  [2] = real callsite (e.g. send_notification_email)
	We skip [0-1] so keys align with business code, not the probe.
	"""
	out: list[dict] = []
	full = inspect.stack()
	start = 2 if len(full) > 2 else 1
	for fr in full[start : start + limit]:
		co = fr.frame.f_code
		mod = fr.frame.f_globals.get("__name__", "")
		entry = {
			"fq_file": getattr(fr, "filename", ""),
			"code_qual": getattr(co, "co_qualname", co.co_name),
			"name": co.co_name,
			"lineno": fr.lineno,
			"module": mod,
		}
		out.append(entry)
	return out


def kwargs_summary(kwargs: dict) -> dict:
	"""Hypothesis H2/H3: shape of outbound mail vs registry targets (no PII secrets)."""
	recipients = kwargs.get("recipients")
	n = len(recipients) if isinstance(recipients, (list, tuple)) else (1 if recipients else 0)
	return {
		"recipient_slot_count": n,
		"has_reference_doctype": bool(kwargs.get("reference_doctype") or kwargs.get("doctype")),
		"has_reference_name": bool(kwargs.get("reference_name") or kwargs.get("name")),
		"has_template": bool(kwargs.get("template")),
		"kw_only_keys_samples": sorted(
			k
			for k in kwargs.keys()
			if k
			not in {"recipients", "message", "content", "subject", "bcc", "cc", "sender", "attachments"}
		)[:12],
	}


def install_sendmail_probe(run_id: str = "bench-discovery") -> Callable[..., Any]:
	"""
	Hypothesis H1: Inspect stack distinguishes notification_log.send_notification_email vs
	                        Notification.send_an_email vs other sendmail callers.
	Hypothesis H2: Keyword shape (reference_*, template) correlates with call site.
	Hypothesis H3: Multiple sendmail invocations per user gesture can be counted by timestamps.
	"""
	global original_sendmail
	import frappe

	if original_sendmail is None:
		original_sendmail = frappe.sendmail

	@functools.wraps(original_sendmail)
	def probe_wrapper(*args, **kwargs) -> Any:
		now_ms = int(time.time() * 1000)
		kw_summary = kwargs_summary(kwargs)
		semantic = stack_frames_for_hypothesis(6)

		print("[bench_sendmail_telemetry] frappe.sendmail — semantic call sites (outermost first):")
		if not semantic:
			print("  (could not resolve stack)")
		else:
			for i, row in enumerate(semantic):
				print(
					f"  [{i}] {row['module']} :: {row['code_qual']}\n" f"       {row['fq_file']}:{row['lineno']}"
				)

		reg0 = registry_keys_for_callsite(semantic[0]) if semantic else {}
		print("[bench_sendmail_telemetry] override hashtable keys (primary callsite [0]):")
		print(f"  module_scope_key:            {reg0.get('module_scope_key')}")
		print(f"  path_scope_key_ast_aligned:  {reg0.get('path_scope_key_ast_aligned')}")

		payload_h1_h2 = {
			"sessionId": SESSION_ID,
			"runId": run_id,
			"hypothesisId": "H1_stack_H2_kwshape",
			"location": "bench_sendmail_telemetry.probe_wrapper",
			"message": "frappe.sendmail invoked",
			"timestamp": now_ms,
			"data": {
				"stack_top6": semantic,
				"kwargs_summary": kw_summary,
				"registry_keys_primary": reg0,
			},
		}
		write_ndjson(payload_h1_h2)

		semantic_top = semantic[:1]
		payload_h3 = {
			"sessionId": SESSION_ID,
			"runId": run_id,
			"hypothesisId": "H3_invoke_tick",
			"location": "bench_sendmail_telemetry.probe_wrapper",
			"message": "sendmail invoke counter anchor",
			"timestamp": now_ms,
			"data": {
				"immediate_callsite_qual": semantic_top[0]["code_qual"] if semantic_top else None,
				"immediate_callsite_module": semantic_top[0]["module"] if semantic_top else None,
				"registry_keys_primary": reg0,
			},
		}
		write_ndjson(payload_h3)

		try:
			return original_sendmail(*args, **kwargs)
		except Exception as e:
			write_ndjson(
				{
					"sessionId": SESSION_ID,
					"runId": run_id,
					"hypothesisId": "H_exc",
					"location": "bench_sendmail_telemetry.probe_wrapper",
					"message": "sendmail raised",
					"timestamp": now_ms,
					"data": {"exc_type": type(e).__name__},
				}
			)
			raise

	frappe.sendmail = probe_wrapper
	install_now = int(time.time() * 1000)
	write_ndjson(
		{
			"sessionId": SESSION_ID,
			"runId": run_id,
			"hypothesisId": "H0_probe_installed",
			"location": "bench_sendmail_telemetry.install_sendmail_probe",
			"message": "sendmail probe installed; log path writable",
			"timestamp": install_now,
			"data": {"debug_log_path": DEBUG_LOG_PATH},
		}
	)
	print(
		f"[bench_sendmail_telemetry] Installed probe. NDJSON logs -> {DEBUG_LOG_PATH} (session={SESSION_ID})"
	)

	return probe_wrapper


def uninstall_sendmail_probe() -> None:
	import frappe

	if original_sendmail is not None:
		frappe.sendmail = original_sendmail


def trigger_demo_sendmail(
	*,
	subject: str | None = None,
	recipient_email: str | None = None,
) -> Any | None:
	"""Fire **frappe.sendmail** from **this module** after :func:`install_sendmail_probe`.

	The semantic stack prints **trigger_demo_sendmail** as callersite **[0]** — no ERP UI needed.
	Use real workflows (mentions, assignments, …) afterward to capture other stacks.

	:param recipient_email: optional; defaults to session user's Email.
	:param subject: mail subject line.
	:raises frappe.exceptions.ValidationError: if no recipient resolves.
	"""
	import frappe

	run_subject = subject or "[bench_sendmail telemetry] probe demo"
	user = getattr(frappe, "session", None) and frappe.session.user
	email = recipient_email or frappe.db.get_value("User", user or "Administrator", "email")
	if not email:
		frappe.throw("No recipient email resolved for bench_sendmail demo.")

	print("[bench_sendmail_telemetry] calling frappe.sendmail via trigger_demo_sendmail …")

	return frappe.sendmail(
		recipients=[email],
		subject=run_subject,
		message="<p>bench_sendmail_telemetry.trigger_demo_sendmail</p>",
		as_markdown=False,
		delayed=False,
		now=True,
	)


# #endregion
