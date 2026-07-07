# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import re

from frappe.core.utils import html2text

SLACK_LINK_RE = re.compile(r"\[(.*?)\]\((.*?)\)")
SLACK_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")
EXCESS_NEWLINES_RE = re.compile(r"\n+")


def convert_html_to_slack_mrkdwn(html: str) -> str:
	"""Convert HTML or markdown-ish text to Slack mrkdwn."""
	if not html:
		return ""

	markdown = html2text(html, strip_links=False, wrap=False)
	markdown = SLACK_BOLD_RE.sub(r"*\1*", markdown)
	markdown = SLACK_LINK_RE.sub(r"<\2|\1>", markdown)
	return EXCESS_NEWLINES_RE.sub("\n", markdown).strip()
