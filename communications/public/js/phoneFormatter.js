// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

// phoneFormatter.js
// Phone formatter using libphonenumber-js for accurate international formatting

import { parsePhoneNumberFromString, AsYouType, getCountries, getExampleNumber } from 'libphonenumber-js'
import examples from 'libphonenumber-js/examples.mobile.json'

/**
 * Phone number formatter using libphonenumber-js
 */
export class PhoneFormatter {
	constructor(options = {}) {
		this.defaultCountry = options.defaultCountry || 'US'
		this.initializePatterns()
	}

	initializePatterns() {
		// Extension patterns that we recognize
		this.extensionPatterns = [
			{ regex: /\s*(?:ext|x)\s*(\d+)$/i, prefix: 'ext', separator: ' ' },
			{ regex: /\s*#\s*(\d+)$/, prefix: '#', separator: '' },
			{ regex: /\s*;\s*(\d+)$/, prefix: ';', separator: '' },
		]

		// Special character patterns for automated systems
		this.specialCharPatterns = [
			{ char: ',', meaning: 'pause', duration: 2 },
			{ char: ';', meaning: 'wait', duration: null },
			{ char: '#', meaning: 'confirm', duration: null },
			{ char: '*', meaning: 'menu', duration: null },
		]
	}

	/**
	 * Parse a phone number string into its components
	 * @param {string} value - The input value to parse
	 * @returns {Object} Parsed phone number components
	 */
	parse(value) {
		const result = {
			countryCode: '',
			country: '',
			nationalNumber: '',
			digits: '',
			extension: '',
			extensionPrefix: '',
			specialChars: '',
			isInternational: false,
			isValid: false,
			phoneNumber: null,
		}

		if (!value) return result

		let workingValue = value

		// Check for international prefix
		if (workingValue.startsWith('+')) {
			result.isInternational = true
		}

		// Extract extension first (before libphonenumber parsing)
		for (const pattern of this.extensionPatterns) {
			const match = workingValue.match(pattern.regex)
			if (match) {
				result.extension = match[1]
				result.extensionPrefix = pattern.prefix
				workingValue = workingValue.substring(0, match.index).trim()
				break
			}
		}

		// Extract special characters (for automated systems)
		const specialMatch = workingValue.match(/([,;]+[\d#*]+)$/)
		if (specialMatch) {
			result.specialChars = specialMatch[1]
			workingValue = workingValue.substring(0, specialMatch.index)
		}

		// Parse with libphonenumber
		try {
			const phoneNumber = parsePhoneNumberFromString(workingValue, this.defaultCountry)
			if (phoneNumber) {
				result.phoneNumber = phoneNumber
				result.countryCode = phoneNumber.countryCallingCode
				result.country = phoneNumber.country || ''
				result.nationalNumber = phoneNumber.nationalNumber
				result.digits = phoneNumber.nationalNumber
				result.isValid = phoneNumber.isValid()

				// If libphonenumber found an extension, use it (unless we already have one)
				if (phoneNumber.ext && !result.extension) {
					result.extension = phoneNumber.ext
					result.extensionPrefix = 'ext'
				}
			} else {
				// If libphonenumber couldn't parse, extract raw digits
				result.digits = workingValue.replace(/\D/g, '')
			}
		} catch (error) {
			// Fallback to simple digit extraction
			result.digits = workingValue.replace(/\D/g, '')
		}

		return result
	}

	/**
	 * Format parsed phone number components for display
	 * @param {Object} parsed - Parsed phone number components
	 * @returns {string} Formatted phone number
	 */
	formatForDisplay(parsed) {
		let formatted = ''

		// Use libphonenumber for formatting if we have a valid phone number object
		if (parsed.phoneNumber) {
			// Format based on whether it's international
			if (parsed.isInternational) {
				formatted = parsed.phoneNumber.formatInternational()
			} else {
				formatted = parsed.phoneNumber.formatNational()
			}
		} else if (parsed.digits) {
			// Fallback formatting for numbers libphonenumber couldn't handle
			if (parsed.isInternational && parsed.countryCode) {
				formatted = `+${parsed.countryCode} ${parsed.digits}`
			} else {
				// Basic US formatting fallback
				if (parsed.digits.length === 10) {
					formatted = parsed.digits.replace(/(\d{3})(\d{3})(\d{4})/, '$1-$2-$3')
				} else {
					formatted = parsed.digits
				}
			}
		}

		// Add extension
		if (parsed.extension) {
			const separator = parsed.extensionPrefix === '#' || parsed.extensionPrefix === ';' ? '' : ' '
			formatted += ` ${parsed.extensionPrefix}${separator}${parsed.extension}`
		}

		// Add special characters
		if (parsed.specialChars) {
			formatted += parsed.specialChars
		}

		return formatted.trim()
	}

	/**
	 * Format a raw value for storage (unformatted digits + extension)
	 * @param {Object} parsed - Parsed phone number components
	 * @returns {string} Storage format
	 */
	formatForStorage(parsed) {
		let storage = ''

		// Include country code for international numbers
		if (parsed.isInternational && parsed.countryCode) {
			storage = `+${parsed.countryCode}`
		}

		// Add national number (digits)
		storage += parsed.nationalNumber || parsed.digits || ''

		// Add extension in compact format
		if (parsed.extension) {
			storage += `x${parsed.extension}`
		}

		// Add special characters as-is
		if (parsed.specialChars) {
			storage += parsed.specialChars
		}

		return storage
	}

	/**
	 * Format a value from storage to display
	 * @param {string} storageValue - The stored value
	 * @returns {string} Display format
	 */
	fromStorage(storageValue) {
		const parsed = this.parse(storageValue)
		return this.formatForDisplay(parsed)
	}

	/**
	 * Format a display value for storage
	 * @param {string} displayValue - The display value
	 * @returns {string} Storage format
	 */
	toStorage(displayValue) {
		const parsed = this.parse(displayValue)
		return this.formatForStorage(parsed)
	}

	/**
	 * Apply formatting to digits as they're typed
	 * @param {string} input - Current input value
	 * @param {number} cursorPos - Current cursor position
	 * @returns {Object} Formatted value and new cursor position
	 */
	formatAsYouType(input, cursorPos = 0) {
		// Handle special cases first
		if (input === '+') {
			return {
				formatted: '+',
				cursorPosition: 1,
				parsed: this.parse(input),
			}
		}

		// Check for extension-only input
		if (input.match(/^(ext|x)\s*\d*$/i)) {
			return {
				formatted: input,
				cursorPosition: cursorPos,
				parsed: this.parse(input),
			}
		}

		// Extract any extension or special chars to preserve them
		let mainNumber = input
		let extension = ''
		let specialChars = ''

		// Check for extension
		for (const pattern of this.extensionPatterns) {
			const match = input.match(pattern.regex)
			if (match) {
				extension = match[0]
				mainNumber = input.substring(0, match.index).trim()
				break
			}
		}

		// Check for special chars
		if (!extension) {
			const specialMatch = mainNumber.match(/([,;]+[\d#*]+)$/)
			if (specialMatch) {
				specialChars = specialMatch[1]
				mainNumber = mainNumber.substring(0, specialMatch.index)
			}
		}

		// Use libphonenumber's AsYouType formatter
		const formatter = new AsYouType(this.defaultCountry)
		let formatted = formatter.input(mainNumber)

		// Re-add extension and special chars
		if (extension) {
			formatted += extension
		}
		if (specialChars) {
			formatted += specialChars
		}

		// Try to maintain cursor position intelligently
		let newCursorPos = cursorPos
		if (formatted.length !== input.length) {
			// If we added characters, move cursor forward
			// If we removed characters, keep cursor in relatively same position
			const diff = formatted.length - input.length
			newCursorPos = Math.max(0, Math.min(cursorPos + diff, formatted.length))
		}

		return {
			formatted,
			cursorPosition: newCursorPos,
			parsed: this.parse(formatted),
		}
	}

	/**
	 * Validate a phone number
	 * @param {string} value - Phone number to validate
	 * @returns {Object} Validation result
	 */
	validate(value) {
		const parsed = this.parse(value)

		const result = {
			isValid: false,
			errors: [],
			parsed,
		}

		// Check if we have any input
		if (!value || !parsed.digits) {
			result.errors.push('No phone number entered')
			return result
		}

		// Use libphonenumber's validation
		if (parsed.phoneNumber) {
			result.isValid = parsed.phoneNumber.isValid()
			if (!result.isValid) {
				// Try to provide more specific error messages
				if (parsed.phoneNumber.isPossible()) {
					result.errors.push('Phone number format is incorrect')
				} else {
					const numberType = parsed.phoneNumber.getType()
					if (numberType === 'TOO_SHORT') {
						result.errors.push('Phone number is too short')
					} else if (numberType === 'TOO_LONG') {
						result.errors.push('Phone number is too long')
					} else {
						result.errors.push('Invalid phone number')
					}
				}
			}
		} else {
			// Fallback validation for numbers libphonenumber couldn't parse
			if (parsed.digits.length < 7) {
				result.errors.push('Phone number is too short')
			} else if (parsed.digits.length > 15) {
				result.errors.push('Phone number is too long')
			} else {
				result.errors.push('Invalid phone number format')
			}
		}

		return result
	}

	/**
	 * Get placeholder for current or specified country
	 * @param {string} country - Optional country code
	 * @returns {string} Placeholder text
	 */
	getPlaceholder(country = null) {
		const targetCountry = country || this.defaultCountry

		try {
			const example = getExampleNumber(targetCountry, examples)
			if (example) {
				return example.formatNational()
			}
		} catch (error) {
			// Fall back to default
		}

		return '(555) 123-4567'
	}

	/**
	 * Calculate cursor position after formatting
	 * This is simplified since libphonenumber handles most complexity
	 */
	calculateCursorPosition(oldValue, newValue, oldCursor, digitCount) {
		// Simple implementation - can be enhanced
		if (!oldValue || !newValue) return newValue.length

		if (oldCursor >= oldValue.length) {
			return newValue.length
		}

		// Try to maintain relative position
		const ratio = oldCursor / oldValue.length
		return Math.round(ratio * newValue.length)
	}
}
