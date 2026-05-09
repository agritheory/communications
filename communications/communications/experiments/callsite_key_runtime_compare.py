# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

#!/usr/bin/env python3
"""
Compare AST-derived stable_key with inspect-based key at runtime (same module, synthetic).

No Frappe bootstrap — verifies the normalization story for registry lookup.
"""

import importlib.util
import inspect
import sys
import tempfile
from pathlib import Path

AST_MODULE_FILE = Path(__file__).resolve().parent / "sendmail_callsites_ast.py"
AST_MODULE_NAME = "communications.communications.experiments.sendmail_callsites_ast"
ast_module_spec = importlib.util.spec_from_file_location(AST_MODULE_NAME, AST_MODULE_FILE)
ast_mod = importlib.util.module_from_spec(ast_module_spec)
assert ast_module_spec.loader
sys.modules[AST_MODULE_NAME] = ast_mod
ast_module_spec.loader.exec_module(ast_mod)


def synthetic_module_source() -> str:
	return """
import builtins

class PretendFrappe:
	@staticmethod
	def sendmail(**kwargs):
		builtins._capturing_sendmail(**kwargs)

frappe = PretendFrappe()

def notify_digest():
	frappe.sendmail(recipients=[], subject="digest")

class NotificationDoc:
	def send_an_email(self):
		frappe.sendmail(recipients=[], subject="x")

def outer():
	def inner_nested():
		frappe.sendmail(recipients=[], subject="nest")
	return inner_nested
"""


def runtime_key_when_sendmail_calls(capture_frame) -> str:
	"""caller of fake frappe.sendmail = one frame below capture_frame."""
	caller = capture_frame.f_back
	assert caller is not None
	mod = caller.f_globals.get("__name__", "?")
	co = caller.f_code
	qual = getattr(co, "co_qualname", co.co_name)
	file = co.co_filename
	return f"{mod}::{qual} (file={file})"


def run_synthetic():
	synthetic_module_src = synthetic_module_source()

	calls_seen: list[str] = []

	def capturing_sendmail(**kwargs):
		f = inspect.currentframe().f_back
		assert f is not None
		calls_seen.append(runtime_key_when_sendmail_calls(f))

	ns: dict = {"builtins": __import__("builtins")}
	ns["builtins"]._capturing_sendmail = capturing_sendmail

	exec(synthetic_module_src, ns)

	ns["notify_digest"]()
	m = ns["NotificationDoc"]()
	m.send_an_email()
	inner_fn = ns["outer"]()
	inner_fn()

	with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
		tmp.write(synthetic_module_src)
		p = Path(tmp.name)
	results, _err = ast_mod.analyze_file(p, package_root=p.parent)

	print("Runtime inspect keys (caller of frappe.sendmail):")
	for i, k in enumerate(calls_seen, 1):
		print(f"  {i}. {k}")
	print("\nAST stable_keys (sorted):")
	for r in sorted(results, key=ast_mod.stable_key):
		print(f"    {ast_mod.stable_key(r)} :: scope={r.logical_scope}")

	print("\nCorrelation (expected 3 AST records for 3 calls):")
	print(f"  AST count: {len(results)}, runtime calls: {len(calls_seen)}")

	return results, calls_seen


if __name__ == "__main__":
	run_synthetic()
