# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

from communications.communications.slack_markdown import convert_html_to_slack_mrkdwn


def test_convert_html_to_slack_mrkdwn_bold():
	result = convert_html_to_slack_mrkdwn("<p><strong>Hello</strong> world</p>")
	assert "*Hello*" in result
	assert "world" in result


def test_convert_html_to_slack_mrkdwn_link():
	result = convert_html_to_slack_mrkdwn('<p><a href="https://example.com">Click here</a></p>')
	assert "<https://example.com|Click here>" in result


def test_convert_html_to_slack_mrkdwn_paragraphs():
	result = convert_html_to_slack_mrkdwn("<p>Line one</p><p>Line two</p>")
	assert "Line one" in result
	assert "Line two" in result
	assert "\n\n" not in result or result.count("\n") <= 2


def test_convert_html_to_slack_mrkdwn_empty():
	assert convert_html_to_slack_mrkdwn("") == ""
	assert convert_html_to_slack_mrkdwn(None) == ""


def test_convert_html_to_slack_mrkdwn_nested_list():
	html = "<ul><li>First</li><li>Second</li></ul>"
	result = convert_html_to_slack_mrkdwn(html)
	assert "First" in result
	assert "Second" in result
