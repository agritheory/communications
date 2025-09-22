// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Twilio Settings', {
	onload: function (frm) {
		frm.set_query('outgoing_voice_medium', function () {
			return {
				filters: {
					communication_channel: 'Twilio',
					communication_medium_type: 'Voice',
				},
			}
		})
	},
})
