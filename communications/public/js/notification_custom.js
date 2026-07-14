// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.provide('frappe.notification')

const DM_NOTIFICATION_CHANNELS = ['Slack DM', 'Teams DM']

frappe.notification.setup_fieldname_select = function (frm) {
	if (!frm.doc.document_type) {
		return
	}

	frappe.model.with_doctype(frm.doc.document_type, function () {
		let get_select_options = function (df, parent_field) {
			let select_value = parent_field ? df.fieldname + ',' + parent_field : df.fieldname

			return {
				value: select_value,
				label: df.fieldname + ' (' + __(df.label, null, df.parent) + ')',
			}
		}

		let get_date_change_options = function () {
			let date_options = $.map(fields, function (d) {
				return d.fieldtype == 'Date' || d.fieldtype == 'Datetime' ? get_select_options(d) : null
			})
			return date_options.concat([
				{ value: 'creation', label: `creation (${__('Created On')})` },
				{ value: 'modified', label: `modified (${__('Last Modified Date')})` },
			])
		}

		let fields = frappe.get_doc('DocType', frm.doc.document_type).fields
		let options = $.map(fields, function (d) {
			return frappe.model.no_value_type.includes(d.fieldtype) ? null : get_select_options(d)
		})

		frm.set_df_property('value_changed', 'options', [''].concat(options))
		frm.set_df_property('set_property_after_alert', 'options', [''].concat(options))
		frm.set_df_property('date_changed', 'options', get_date_change_options())

		let receiver_fields = []
		if (frm.doc.channel === 'Email' || DM_NOTIFICATION_CHANNELS.includes(frm.doc.channel)) {
			receiver_fields = $.map(fields, function (d) {
				if (frappe.model.table_fields.includes(d.fieldtype)) {
					let child_fields = frappe.get_doc('DocType', d.options).fields
					return $.map(child_fields, function (df) {
						return df.options == 'Email' || (df.options == 'User' && df.fieldtype == 'Link')
							? get_select_options(df, d.fieldname)
							: null
					})
				} else {
					return d.options == 'Email' || (d.options == 'User' && d.fieldtype == 'Link') ? get_select_options(d) : null
				}
			})
		} else if (['WhatsApp', 'SMS'].includes(frm.doc.channel)) {
			receiver_fields = $.map(fields, function (d) {
				return d.options == 'Phone' ? get_select_options(d) : null
			})
		}

		frm.fields_dict.recipients.grid.update_docfield_property(
			'receiver_by_document_field',
			'options',
			[''].concat(['owner']).concat(receiver_fields)
		)

		let attach_fields = fields.filter(d => ['Attach', 'Attach Image'].includes(d.fieldtype))
		let attach_options = $.map(attach_fields, function (d) {
			return get_select_options(d)
		})

		frm.set_df_property('from_attach_field', 'options', [''].concat(attach_options))
	})
}
