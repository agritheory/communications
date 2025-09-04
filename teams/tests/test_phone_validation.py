# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import pytest
import frappe
from unittest.mock import Mock
from teams.teams import validate_phone_number, PHONE_NUMBER_PATTERN


def test_standard_north_american_formats():
	"""Test standard North American phone number formats"""
	# 1. with parentheses and dash
	assert validate_phone_number("(555) 123-4567") is True

	# 2. with dashes
	assert validate_phone_number("555-123-4567") is True

	# 3. with dots
	assert validate_phone_number("555.123.4567") is True

	# 4. with spaces
	assert validate_phone_number("555 123 4567") is True

	# 5. no separators
	assert validate_phone_number("5551234567") is True


def test_international_formats():
	"""Test international phone number formats"""
	# 6. with +1 country code
	assert validate_phone_number("+1 555 123 4567") is True

	# 7. UK country code
	assert validate_phone_number("+44 555 123 4567") is True

	# 8. France country code
	assert validate_phone_number("+33 555 123 4567") is True

	# 9. China country code
	assert validate_phone_number("+86 555 123 4567") is True

	# 10. 4-digit country code
	assert validate_phone_number("+1234 555 123 4567") is True


def test_with_extensions():
	"""Test phone numbers with extensions"""
	# 11. with "ext"
	assert validate_phone_number("555-123-4567 ext 123") is True

	# 12. with "ext."
	assert validate_phone_number("555-123-4567 ext. 456") is True

	# 13. with "x"
	assert validate_phone_number("555-123-4567 x789") is True

	# 14. 6-digit extension
	assert validate_phone_number("(555) 123-4567 ext 123456") is True


def test_mobile_special_characters():
	"""Test mobile device special characters"""
	# 15. with pause (comma)
	assert validate_phone_number("555-123-4567,123") is True

	# 16. with wait (semicolon)
	assert validate_phone_number("555-123-4567;456") is True

	# 17. with pause (p)
	assert validate_phone_number("555-123-4567p789") is True

	# 18. with wait (w)
	assert validate_phone_number("555-123-4567w012") is True

	# 19. with pause (uppercase P)
	assert validate_phone_number("555-123-4567P345") is True

	# 20. with wait (uppercase W)
	assert validate_phone_number("555-123-4567W678") is True

	# 21. with hash
	assert validate_phone_number("555-123-4567#901") is True

	# 22. with star
	assert validate_phone_number("555-123-4567*234") is True

	# 23. multiple pauses
	assert validate_phone_number("555-123-4567,123,456") is True

	# 24. combined wait and hash
	assert validate_phone_number("555-123-4567;1#234") is True


def test_combined_features():
	"""Test combinations of international, extensions, and special characters"""
	# 25. international with extension
	assert validate_phone_number("+1 (555) 123-4567 ext 123") is True

	# 26. international with pause
	assert validate_phone_number("+44 555-123-4567,123") is True

	# 27. pause and extension
	assert validate_phone_number("555-123-4567,123 ext 456") is True


def test_invalid_phone_numbers():
	"""Test invalid phone number formats"""
	# 1. too short (missing area code)
	assert validate_phone_number("123-4567") is False

	# 2. invalid area code (2 digits)
	assert validate_phone_number("(55) 123-4567") is False

	# 3. invalid area code (4 digits)
	assert validate_phone_number("(5555) 123-4567") is False

	# 4. invalid middle section (2 digits)
	assert validate_phone_number("555-12-4567") is False

	# 5. invalid last section (3 digits)
	assert validate_phone_number("555-1234-567") is False

	# 6. too short last section
	assert validate_phone_number("555-123-456") is False

	# 7. too long last section
	assert validate_phone_number("555-123-45678") is False

	# 8. invalid country code (starts with 0)
	assert validate_phone_number("+0 555 123 4567") is False

	# 9. country code too long (5 digits)
	assert validate_phone_number("+12345 555 123 4567") is False

	# 10. invalid extension prefix
	assert validate_phone_number("555-123-4567 extension 123") is False

	# 11. extension too long (7 digits)
	assert validate_phone_number("555-123-4567 ext 1234567") is False

	# 12. letters instead of numbers
	assert validate_phone_number("abc-def-ghij") is False

	# 13. trailing special character without digits
	assert validate_phone_number("555 123 4567 ,") is False

	# 14. empty string
	assert validate_phone_number("") is False

	# 15. None value
	assert validate_phone_number(None) is False


def test_edge_cases():
	"""Test edge cases and boundary conditions"""
	# 1. Leading/trailing whitespace (should be stripped)
	assert validate_phone_number("  555-123-4567  ") is True

	# 2. Mixed separators
	assert validate_phone_number("(555)-123.4567") is True

	# 3a. No opening parenthesis
	assert validate_phone_number("555) 123-4567") is False

	# 3b. No closing parenthesis
	assert validate_phone_number("(555 123-4567") is False


def test_throw_parameter():
	"""Test the throw parameter for invalid phone numbers"""
	# Should raise frappe.InvalidPhoneNumberError for invalid number with throw=True
	with pytest.raises(frappe.InvalidPhoneNumberError) as exc_info:
		validate_phone_number("invalid-phone", throw=True)

	assert "invalid-phone is not a valid Phone Number" in str(exc_info.value)

	# Should not raise for valid number with throw=True
	assert validate_phone_number("555-123-4567", throw=True) is True

	# Should not raise for invalid number with throw=False (default)
	assert validate_phone_number("invalid-phone", throw=False) is False


def test_monkey_patch_is_applied():
	"""Test that the monkey patch is correctly applied to frappe.utils"""
	import frappe.utils
	from teams.teams import validate_phone_number as our_validator

	# Verify that frappe.utils.validate_phone_number is our function
	assert frappe.utils.validate_phone_number is our_validator

	# Test that our patched version works with extensions (original wouldn't)
	assert frappe.utils.validate_phone_number("555-123-4567 ext 123") is True

	# Test that our patched version works with mobile special chars
	assert frappe.utils.validate_phone_number("555-123-4567,123") is True


def test_validate_data_fields_integration():
	"""Test integration with _validate_data_fields method"""
	from teams.teams import _validate_data_fields

	# Create mock document with phone field
	mock_doc = Mock()
	mock_doc.meta = Mock()
	mock_doc.owner = "test@example.com"

	# Setup phone field with proper options structure
	phone_field = Mock()
	phone_field.fieldname = "phone"
	phone_field.get = Mock(return_value="Phone")  # options is returned via get()
	phone_field.options = "Phone"

	# Setup for get("oldfieldtype")
	phone_field.get.side_effect = lambda key: "Phone" if key == "options" else None

	# Setup data fields
	mock_doc.meta.get_phone_fields = Mock(return_value=[])
	mock_doc.meta.get_data_fields = Mock(return_value=[phone_field])

	# Test with valid phone number with extension
	mock_doc.get = Mock(return_value="555-123-4567 ext 123")

	# Should not raise any exception
	try:
		_validate_data_fields(mock_doc)
	except Exception as e:
		pytest.fail(f"Valid phone with extension raised exception: {e}")

	# Test with invalid phone number
	mock_doc.get = Mock(return_value="invalid-phone")

	# Should raise InvalidPhoneNumberError
	with pytest.raises(frappe.InvalidPhoneNumberError):
		_validate_data_fields(mock_doc)


def test_regex_pattern_directly():
	"""Test the PHONE_NUMBER_PATTERN regex directly"""
	# Valid patterns (formatted)
	valid_formatted = [
		"(555) 123-4567",
		"+1 555 123 4567",
		"555-123-4567,123",
		"555-123-4567 ext 123",
	]

	for number in valid_formatted:
		match = PHONE_NUMBER_PATTERN.match(number)
		assert match is not None, f"Pattern should match formatted: {number}"

	# Valid patterns (as stored in DB - stripped)
	valid_stripped = [
		"5551234567",
		"+15551234567",
		"5551234567,123",
		"5551234567ext123",
		"+445551234567w456",
		"5551234567#789",
	]

	for number in valid_stripped:
		match = PHONE_NUMBER_PATTERN.match(number)
		assert match is not None, f"Pattern should match stripped: {number}"

	# Invalid patterns
	invalid_numbers = [
		"1234567",  # too short
		"abc-def-ghij",  # letters
		"+0 555 123 4567",  # invalid country code
		"5551234567extension123",  # invalid extension prefix
	]

	for number in invalid_numbers:
		match = PHONE_NUMBER_PATTERN.match(number)
		assert match is None, f"Pattern should not match: {number}"
