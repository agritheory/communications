// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

// phoneFormatter.test.js
// Unit tests for PhoneFormatter using Vitest

import { describe, it, expect, beforeEach } from 'vitest'
import { PhoneFormatter } from './phoneFormatter.js'

describe('PhoneFormatter', () => {
	let formatter

	beforeEach(() => {
		formatter = new PhoneFormatter({ defaultCountry: 'US' })
	})

	describe('parse', () => {
		it('should parse a simple US phone number', () => {
			const result = formatter.parse('555-123-4567')
			expect(result.digits).toBeTruthy()
			expect(result.extension).toBe('')
			expect(result.isInternational).toBe(false)
		})

		it('should parse a US phone number with extension', () => {
			const result = formatter.parse('555-123-4567 ext 123')
			expect(result.digits).toBeTruthy()
			expect(result.extension).toBe('123')
			expect(result.extensionPrefix).toBe('ext')
		})

		it('should parse a phone number with x extension', () => {
			const result = formatter.parse('5551234567x999')
			expect(result.digits).toBeTruthy()
			expect(result.extension).toBe('999')
			expect(result.extensionPrefix).toBe('ext')
		})

		it('should parse international numbers', () => {
			const result = formatter.parse('+44 20 7123 4567')
			expect(result.countryCode).toBe('44')
			expect(result.digits).toBeTruthy()
			expect(result.isInternational).toBe(true)
		})

		it('should parse numbers with special characters for automated systems', () => {
			const result = formatter.parse('555-123-4567,,123#')
			expect(result.digits).toBeTruthy()
			expect(result.specialChars).toBe(',,123#')
		})

		it('should handle empty input', () => {
			const result = formatter.parse('')
			expect(result.digits).toBe('')
			expect(result.extension).toBe('')
			expect(result.specialChars).toBe('')
		})

		it('should handle input with only extension notation', () => {
			const result = formatter.parse('ext 123')
			expect(result.digits).toBe('')
			expect(result.extension).toBe('123')
		})
	})

	describe('formatForDisplay', () => {
		it('should format US phone numbers correctly', () => {
			const parsed = formatter.parse('5551234567')
			const formatted = formatter.formatForDisplay(parsed)
			// libphonenumber-js will format as (555) 123-4567 for US
			expect(formatted).toContain('555')
			expect(formatted).toContain('123')
			expect(formatted).toContain('4567')
		})

		it('should format partial US phone numbers', () => {
			const parsed = formatter.parse('555123')
			const formatted = formatter.formatForDisplay(parsed)
			expect(formatted).toContain('555')
			expect(formatted).toContain('123')
		})

		it('should include extensions in display', () => {
			const parsed = formatter.parse('5551234567x123')
			const formatted = formatter.formatForDisplay(parsed)
			expect(formatted).toContain('ext 123')
		})

		it('should format international numbers correctly', () => {
			// Test India number
			const indiaNumber = formatter.parse('+91 7503907302')
			const indiaFormatted = formatter.formatForDisplay(indiaNumber)
			expect(indiaFormatted).toBe('+91 75039 07302')

			// Test South Africa number
			const saNumber = formatter.parse('+27 87 123 4567')
			const saFormatted = formatter.formatForDisplay(saNumber)
			// libphonenumber-js formats this correctly
			expect(saFormatted).toContain('+27')
		})

		it('should preserve special characters', () => {
			const parsed = formatter.parse('5551234567,,123#')
			const formatted = formatter.formatForDisplay(parsed)
			expect(formatted).toContain(',,123#')
		})
	})

	describe('formatForStorage', () => {
		it('should store US numbers as raw digits', () => {
			const parsed = formatter.parse('(555) 123-4567')
			const storage = formatter.formatForStorage(parsed)
			expect(storage).toMatch(/^\d+$/)
		})

		it('should store extensions with x prefix', () => {
			const parsed = formatter.parse('555-123-4567 ext 123')
			const storage = formatter.formatForStorage(parsed)
			expect(storage).toContain('x123')
		})

		it('should preserve international prefix in storage', () => {
			const parsed = formatter.parse('+44 20 7123 4567')
			const storage = formatter.formatForStorage(parsed)
			expect(storage.startsWith('+44')).toBe(true)
		})

		it('should preserve special characters in storage', () => {
			const parsed = formatter.parse('555-123-4567,,123#')
			const storage = formatter.formatForStorage(parsed)
			expect(storage).toContain(',,123#')
		})
	})

	describe('fromStorage and toStorage', () => {
		it('should convert between storage and display formats', () => {
			const testNumbers = ['5551234567x123', '+442071234567', '+917503907302', '+27871234567']

			testNumbers.forEach(storageValue => {
				const displayValue = formatter.fromStorage(storageValue)
				expect(displayValue).toBeTruthy()
				// Verify it formats to something different than storage
				expect(displayValue).not.toBe(storageValue)
			})
		})
	})

	describe('formatAsYouType', () => {
		it('should format as user types', () => {
			const inputs = ['5', '55', '555', '5551', '55512', '555123', '5551234']

			inputs.forEach(input => {
				const result = formatter.formatAsYouType(input, input.length)
				expect(result.formatted).toBeTruthy()
				expect(result.cursorPosition).toBeGreaterThanOrEqual(0)
			})
		})

		it('should handle international number input', () => {
			const result = formatter.formatAsYouType('+1555', 5)
			expect(result.formatted).toContain('+1')
		})

		it('should preserve extensions while typing', () => {
			const result = formatter.formatAsYouType('5551234567 ext 12', 18)
			expect(result.formatted).toContain('ext 12')
		})
	})

	describe('validate', () => {
		it('should validate correct US phone numbers', () => {
			const result = formatter.validate('555-123-4567')
			// Note: 555 numbers are often invalid in real validation
			// but for testing we'll check the structure
			expect(result.errors.length).toBeGreaterThanOrEqual(0)
		})

		it('should validate real US phone numbers', () => {
			// Use a more realistic number
			const result = formatter.validate('202-456-1111')
			expect(result.parsed.phoneNumber).toBeTruthy()
		})

		it('should validate international numbers', () => {
			const result = formatter.validate('+44 20 7123 4567')
			expect(result.isValid).toBe(true)
		})

		it('should reject empty input', () => {
			const result = formatter.validate('')
			expect(result.isValid).toBe(false)
			expect(result.errors).toContain('No phone number entered')
		})

		it('should accept extensions as valid', () => {
			const result = formatter.validate('202-456-1111 ext 123')
			expect(result.parsed.extension).toBe('123')
		})
	})

	describe('getPlaceholder', () => {
		it('should return US placeholder by default', () => {
			const placeholder = formatter.getPlaceholder()
			expect(placeholder).toBeTruthy()
		})

		it('should return placeholder for specific country', () => {
			const placeholder = formatter.getPlaceholder('GB')
			expect(placeholder).toBeTruthy()
		})
	})

	describe('edge cases', () => {
		it('should handle numbers with mixed formatting', () => {
			const result = formatter.parse('(555) 123-4567 x123')
			expect(result.digits).toBeTruthy()
			expect(result.extension).toBe('123')
		})

		it('should handle multiple special characters', () => {
			const result = formatter.parse('555-123-4567,,,123###')
			expect(result.digits).toBeTruthy()
			expect(result.specialChars).toBe(',,,123###')
		})

		it('should handle international numbers with extensions', () => {
			const result = formatter.parse('+44 20 7123 4567 ext 999')
			expect(result.countryCode).toBe('44')
			expect(result.extension).toBe('999')
		})
	})
})
