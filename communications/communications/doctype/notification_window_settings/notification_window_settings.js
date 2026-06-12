// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Notification Window Settings', {
	before_load: function (frm) {
		let update_tz_options = function () {
			frm.fields_dict.time_zone.set_data(frappe.all_timezones)
		}

		if (!frappe.all_timezones) {
			frappe.call({
				method: 'frappe.core.doctype.user.user.get_timezones',
				callback: function (r) {
					frappe.all_timezones = r.message.timezones
					update_tz_options()
				},
			})
		} else {
			update_tz_options()
		}
	},
	time_zone: function (frm) {
		if (frm.doc.time_zone && frm.doc.time_zone.startsWith('Etc')) {
			frm.set_df_property('time_zone', 'description', __('Note: Etc timezones have their signs reversed.'))
		}
	},
})
