// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

import { PhoneField } from './phoneField.js'

frappe.ui.form.ControlData = class CustomControlData extends frappe.ui.form.ControlData {
	make_input() {
		super.make_input()

		if (this.df.options === 'Phone') {
			this.phoneField = new PhoneField(this)
		}
	}

	refresh() {
		super.refresh()
		if (this.phoneField && this.$callButton) {
			this.phoneField.updateButtonState()
		}
	}

	remove() {
		if (this.phoneField) {
			this.phoneField.destroy()
		}
		super.remove()
	}
}
