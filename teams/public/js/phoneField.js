// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

import { PhoneFormatter } from './phoneFormatter.js'

export class PhoneField {
	constructor(controlData) {
		this.control = controlData
		this.$input = controlData.$input
		this.$wrapper = controlData.$wrapper
		this.doctype = controlData.doctype
		this.docname = controlData.docname

		this.formatter = new PhoneFormatter({
			defaultCountry: frappe.boot.sysdefaults.country_code || 'US',
		})

		this.isFormatting = false
		this.previousValue = ''

		this.setupWrapper()
		this.setupCallButton()
		this.setupValueProxy()
		this.bindEvents()
		this.addStyles()

		if (this.$input.val()) {
			this.formatInitialValue()
		}
	}

	setupWrapper() {
		const $wrapper = $('<div class="input-group phone-input-group"></div>')
		const $inputWrapper = $('<div class="input-group-prepend flex-grow-1"></div>')

		this.$input.wrap($wrapper)
		this.$input.wrap($inputWrapper)
	}

	setupCallButton() {
		const $callButton = $(`
			<div class="input-group-append">
				<button class="btn btn-call"
					type="button"
					title="Call this number"
					aria-label="Call this number"
					tabindex="0">
					<i class="fa fa-phone"></i>
				</button>
			</div>
		`)

		this.$input.closest('.input-group-prepend').after($callButton)
		this.$callButton = $callButton.find('.btn-call')

		this.$callButton.on('click', () => this.makeCall())
		this.$callButton.on('keydown', e => {
			if (e.key === 'Enter' || e.key === ' ') {
				e.preventDefault()
				this.makeCall()
			}
		})
	}

	setupValueProxy() {
		// Store original jQuery val method
		const originalVal = $.fn.val
		const self = this

		// Create proxy for val method
		this.$input.val = function (value) {
			if (arguments.length === 0) {
				// Getting value - return storage format
				const displayValue = originalVal.call(this)
				if (displayValue) {
					return self.formatter.toStorage(displayValue)
				}
				return displayValue
			} else {
				// Setting value - format for display
				if (value) {
					const formatted = self.formatter.fromStorage(value)
					return originalVal.call(this, formatted)
				}
				return originalVal.call(this, value)
			}
		}

		// Also intercept get_input_value if it exists
		if (this.control.get_input_value) {
			const originalGetInputValue = this.control.get_input_value.bind(this.control)
			this.control.get_input_value = function () {
				const value = originalGetInputValue()
				if (value) {
					return self.formatter.toStorage(value)
				}
				return value
			}
		}
	}

	bindEvents() {
		this.$input.on('input', e => this.handleInput(e))
		this.$input.on('paste', e => this.handlePaste(e))
		this.$input.on('blur', () => this.handleBlur())
		this.$input.on('focus', () => this.handleFocus())
		this.$input.on('change', () => this.updateButtonState())
	}

	handleInput(e) {
		if (this.isFormatting) return

		const input = e.target
		const value = input.value
		const cursorPos = input.selectionStart

		// Check if user is typing special characters that indicate they're not done
		// Allow free typing for: +, ext, x, commas, etc.
		const isTypingSpecial = /[+ext,;#*]$/i.test(value)
		const hasIncompleteExtension = /\s+(e|ex|ext?)$/i.test(value)
		const isStartingInternational = value === '+'

		// If user is in the middle of typing something special, don't format yet
		if (isTypingSpecial || hasIncompleteExtension || isStartingInternational) {
			this.previousValue = value
			// Still validate to show warning while typing
			this.validatePhone(true)
			return
		}

		// Only format if we have a somewhat complete number or pattern
		const digits = value.replace(/\D/g, '')
		if (digits.length < 3 && !value.includes('ext') && !value.includes('x')) {
			this.previousValue = value
			this.validatePhone(true)
			return
		}

		this.isFormatting = true

		// Format the input
		const result = this.formatter.formatAsYouType(value, cursorPos)

		if (result.formatted !== value) {
			input.value = result.formatted

			if (input.setSelectionRange) {
				input.setSelectionRange(result.cursorPosition, result.cursorPosition)
			}
		}

		this.previousValue = result.formatted
		this.validatePhone(true)
		this.$input.trigger('change')
		this.isFormatting = false
	}

	handlePaste(e) {
		e.preventDefault()
		const pastedText = (e.originalEvent.clipboardData || window.clipboardData).getData('text')

		if (pastedText) {
			const parsed = this.formatter.parse(pastedText)
			const formatted = this.formatter.formatForDisplay(parsed)
			const originalVal = $.fn.val
			originalVal.call(this.$input, formatted)
			this.previousValue = formatted
			this.validatePhone(true)
			this.$input.trigger('change')
		}
	}

	handleBlur() {
		this.validatePhone(false)
	}

	handleFocus() {
		const placeholder = this.formatter.getPlaceholder()
		this.$input.attr('placeholder', placeholder)

		if (this.$input.val() && this.$input[0].setSelectionRange) {
			setTimeout(() => {
				this.$input[0].setSelectionRange(0, this.$input.val().length)
			}, 0)
		}

		this.validatePhone(true)
	}

	formatInitialValue() {
		const value = this.$input.val()
		if (value) {
			const formatted = this.formatter.fromStorage(value)
			const originalVal = $.fn.val
			originalVal.call(this.$input, formatted)
			this.previousValue = formatted
		}
	}

	validatePhone(isFocused = false) {
		const displayValue = this.$input.val()
		if (!displayValue) {
			this.clearValidation()
			return true
		}

		const validation = this.formatter.validate(displayValue)

		if (validation.isValid) {
			this.$input.removeClass('invalid-phone warning-phone')
			this.$wrapper.find('.phone-validation-message').remove()
		} else {
			if (isFocused) {
				this.$input.removeClass('invalid-phone').addClass('warning-phone')
			} else {
				this.$input.removeClass('warning-phone').addClass('invalid-phone')
			}

			this.$wrapper.find('.phone-validation-message').remove()
		}
		return validation.isValid
	}

	clearValidation() {
		this.$input.removeClass('invalid-phone warning-phone')
		this.$wrapper.find('.phone-validation-message').remove()
	}

	updateButtonState() {
		const value = this.$input.val()
		const parsed = this.formatter.parse(value)
		const hasValue = Boolean(parsed.digits)

		this.$callButton.prop('disabled', !hasValue)

		if (!hasValue) {
			this.$callButton.attr('title', 'Enter a phone number first')
		} else {
			this.$callButton.attr('title', `Call ${value}`)
		}
	}

	makeCall() {
		const inputValue = this.$input.val()
		const parsed = this.formatter.parse(inputValue)

		if (!parsed.digits) {
			frappe.msgprint(__('Please enter a phone number first'))
			return
		}

		const displayValue = this.formatter.formatForDisplay(parsed)

		// Build the call number
		let callNumber = parsed.digits
		if (parsed.extension) {
			callNumber += ',' + parsed.extension // Add pause before extension
		}
		if (parsed.specialChars) {
			callNumber += parsed.specialChars
		}

		const d = new frappe.ui.Dialog({
			title: __('Call with Teams', null, ''),
			primary_action_label: __('Call with Teams', null, 'Call with Teams'),
			primary_action: () => {
				frappe.call({
					method: 'teams.teams.start_teams_call',
					args: {
						phone_number: callNumber,
						doctype: this.doctype,
						docname: this.docname,
					},
				})
				d.hide()
			},
			secondary_action_label: __('Call with Telephone', null, 'Call with Telephone'),
			secondary_action: () => {
				window.location.href = `tel:${callNumber}`
				d.hide()
			},
		})

		d.$body.append(`<p class="frappe-confirm-message">Call ${displayValue} with Teams</p>`)
		d.show()
		d.confirm_dialog = true
	}

	addStyles() {
		if (!$('#phone-field-styles').length) {
			$('head').append(`
				<style id="phone-field-styles">
					/* Phone input group using Frappe v15 structure */
					.phone-input-group {
						display: flex;
						width: 100%;
						position: relative;
					}

					.phone-input-group .input-group-prepend {
						flex: 1;
						display: flex;
						min-width: 0;
					}

					.phone-input-group .input-group-prepend input {
						border-top-right-radius: 0 !important;
						border-bottom-right-radius: 0 !important;
					}

					.phone-input-group .input-group-append {
						display: flex;
						flex-shrink: 0;
					}

					/* Call button inheriting Frappe styles */
					.phone-input-group .btn-call {
						border-top-left-radius: 0;
						border-bottom-left-radius: 0;
						border: 2px solid transparent;
						border-left: none;
						outline-right: none;
						padding: 0 var(--padding-sm);
						height: var(--input-height);
						min-height: var(--input-height);
						background-color: var(--control-bg);
						color: var(--text-muted);
						cursor: pointer;
						display: flex;
						align-items: center;
						justify-content: center;
						font-size: inherit;
						line-height: 1;
						box-sizing: border-box;
					}

					/* Hover state */
					.phone-input-group .btn-call:hover:not(:disabled) {
						background-color: var(--gray-300);
						color: var(--text-muted);
						outline: 2px solid var(--gray-300);
						outline-left: none;
					}

					/* Ensure button border matches when focused */
					.phone-input-group:focus-within .btn-call {
						outline: 2px solid var(--gray-300);
						outline-left: none;
					}
				</style>
			`)
		}
	}

	destroy() {
		this.$input.off('input paste blur focus change')
		this.$callButton.off('click keydown')
	}
}
