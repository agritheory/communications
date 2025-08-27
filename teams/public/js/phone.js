// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.ControlData = class CustomControlData extends frappe.ui.form.ControlData {
	make_input() {
		super.make_input()

		if (this.df.options === 'Phone') {
			this.setup_phone_field()
		}
	}

	setup_phone_field() {
		const $wrapper = $('<div class="input-group"></div>')
		const $inputWrapper = $('<div class="input-group-prepend flex-grow-1"></div>')

		this.$input.wrap($wrapper)
		this.$input.wrap($inputWrapper)
		const $callButton = $(`
			<div class="input-group-append">
				<button class="btn btn-default btn-call" type="button" title="Call">
					<i class="fa fa-phone"></i>
				</button>
			</div>
		`)

		this.$input.closest('.input-group-prepend').after($callButton)

		$callButton.find('.btn-call').on('click', () => {
			this.make_call()
		})

		this.$input.css({
			'border-right': 'none',
			'border-top-right-radius': '0',
			'border-bottom-right-radius': '0',
		})
	}

	make_call() {
		const phoneNumber = this.get_value()

		if (!phoneNumber) {
			frappe.msgprint(__('Please enter a phone number first'))
			return
		}

		const cleanNumber = phoneNumber.replace(/[\s\-\(\)]/g, '')

		var d = new frappe.ui.Dialog({
			title: __('Call with Teams', null, ''),
			primary_action_label: __('Call with Teams', null, 'Call with Teams'),
			primary_action: () => {
				frappe.call({
					method: 'teams.teams.start_teams_call',
					args: {
						phone_number: cleanNumber,
						doctype: this.doctype,
						docname: this.docname,
					},
				})
				d.hide()
			},
			secondary_action_label: __('Call with Telephone', null, 'Call with Telephone'),
			secondary_action: () => {
				window.location.href = `tel:${cleanNumber}`
				d.hide()
			},
		})

		d.$body.append(`<p class="frappe-confirm-message">Call ${phoneNumber} with Teams</p>`)
		d.show()
		d.confirm_dialog = true
	}
}
