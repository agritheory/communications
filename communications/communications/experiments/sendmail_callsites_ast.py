# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

#!/usr/bin/env python3
"""
Experiment: derive stable-ish keys for frappe.sendmail / sendmail call sites using AST only
(no lineno in the advertised key — disambiguate with ordinal within same scope).

Run from repo root (apps):
  python3 communications/communications/communications/experiments/sendmail_callsites_ast.py [paths...]

Paths default to ../../frappe/frappe relative to this file (requires sibling frappe app checkout).
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator

# experiments/ -> triple-nested communications/ -> app checkout root -> apps
COMMUNICATIONS_APP_ROOT = Path(__file__).resolve().parents[3]
APPS_ROOT = Path(__file__).resolve().parents[4]


def is_sendmail_like_call(node: ast.Call) -> bool:
	"""
	Recognize:
	  - frappe.sendmail(...)  — Frappe enqueue path
	  - bare sendmail(...)    — uncommon; local alias to frappe.sendmail

	Exclude smtplib/session sendmail — those are Attribute(sendmail) on non-frappe receivers.
	"""
	fn = node.func
	if isinstance(fn, ast.Attribute) and fn.attr == "sendmail":
		base = fn.value
		return isinstance(base, ast.Name) and base.id == "frappe"
	if isinstance(fn, ast.Name):
		return fn.id == "sendmail"
	return False


@dataclass(frozen=True)
class CallSiteRecord:
	module_path_from_file: str
	package_prefix: str
	logical_scope: str
	idx_in_scope: int
	docstring_hint: str


class SendmailLocator(ast.NodeVisitor):
	def __init__(self, file_path: Path, package_root: Path):
		self.file_path = file_path
		try:
			rel_to_pkg = file_path.resolve().relative_to(package_root.resolve())
		except ValueError:
			rel_to_pkg = file_path
		self.module_path_from_file = str(rel_to_pkg.as_posix())
		parts = rel_to_pkg.with_suffix("").parts
		self.package_prefix = ".".join(parts) if parts else ""
		self._scopes: list[str] = []
		self.results: list[CallSiteRecord] = []
		self._per_scope_count: dict[str, int] = {}

	def scope_qualname(self) -> str:
		return ".".join(self._scopes) if self._scopes else "<module>"

	def bump_scope_index(self, scope_key: str) -> int:
		self._per_scope_count[scope_key] = self._per_scope_count.get(scope_key, 0) + 1
		return self._per_scope_count[scope_key]

	def visit_ClassDef(self, node: ast.ClassDef) -> None:
		self._scopes.append(node.name)
		self.generic_visit(node)
		self._scopes.pop()

	def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
		self._scopes.append(node.name)
		self.generic_visit(node)
		self._scopes.pop()

	def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
		self._scopes.append(node.name)
		self.generic_visit(node)
		self._scopes.pop()

	def visit_Call(self, node: ast.Call) -> None:
		if not is_sendmail_like_call(node):
			return
		q = self.scope_qualname()
		file_scope_key = f"{self.package_prefix}::{q}"
		idx = self.bump_scope_index(file_scope_key)
		hint = f"in {'.'.join(self._scopes)}" if self._scopes else ""
		self.results.append(
			CallSiteRecord(
				module_path_from_file=self.module_path_from_file,
				package_prefix=self.package_prefix,
				logical_scope=q,
				idx_in_scope=idx,
				docstring_hint=hint,
			)
		)
		self.generic_visit(node)


def discover_py_files(paths: list[Path]) -> Iterator[Path]:
	for root in paths:
		if root.is_file() and root.suffix == ".py":
			yield root
		elif root.is_dir():
			for p in root.rglob("*.py"):
				if "__pycache__" not in str(p.parts):
					yield p


def stable_key(record: CallSiteRecord) -> str:
	"""Logical key: dotted path derived from dirs + enclosing ast scope + nth call in scope."""
	if record.idx_in_scope > 1:
		return f"{record.package_prefix}::{record.logical_scope}@{record.idx_in_scope}"
	return f"{record.package_prefix}::{record.logical_scope}"


def analyze_file(py_file: Path, package_root: Path) -> tuple[list[CallSiteRecord], str | None]:
	try:
		src = py_file.read_text(encoding="utf-8")
	except OSError:
		return [], "read_failed"
	tree = ast.parse(src, filename=str(py_file))
	v = SendmailLocator(py_file, package_root)
	v.visit(tree)
	return v.results, None


def main() -> None:
	frappe_pkg = APPS_ROOT / "frappe" / "frappe"
	if not frappe_pkg.is_dir():
		print(
			f"Expected Frappe app at {frappe_pkg}; pass explicit path(s) to scan.",
			file=sys.stderr,
		)
		sys.exit(1)
	paths = [Path(a).resolve() for a in sys.argv[1:]] if len(sys.argv) > 1 else [frappe_pkg]
	all_found: list[tuple[Path, CallSiteRecord]] = []
	for pf in discover_py_files(paths):
		recs, err = analyze_file(pf, package_root=frappe_pkg.parent)
		if err:
			continue
		for r in recs:
			all_found.append((pf, r))

	all_found.sort(key=lambda t: stable_key(t[1]))

	print(f"Roots: {[str(p) for p in paths]}")
	print(f"Heuristic sendmail/frappe.sendmail calls: {len(all_found)}\n")
	prev_key = None
	for path, rec in all_found:
		key = stable_key(rec)
		dup_marker = "*" if key == prev_key else " "
		prev_key = key
		print(f"{dup_marker} {key}")
		print(f"    file: {rec.module_path_from_file}")

	want = {"notification_log", "notification/", "workflow_action"}
	print("\n--- Filter (interesting paths) ---")
	for path, rec in all_found:
		sp = path.as_posix()
		if any(w in sp for w in want):
			print(f"  {stable_key(rec)}")
			print(f"      {path}")


if __name__ == "__main__":
	main()
