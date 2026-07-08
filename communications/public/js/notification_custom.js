// Copyright (c) 2026, AgriTheory and contributors
// For license information, please see license.txt

frappe.provide('frappe.notification')

const DM_CHANNELS = ['Slack DM', 'Teams DM']
const MARKDOWN_EXAMPLE_CHANNELS = ['Slack', 'System Notification', 'SMS', ...DM_CHANNELS]

function uses_email_receiver_fields(channel) {
	return channel === 'Email' || DM_CHANNELS.includes(channel)
}

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
		if (uses_email_receiver_fields(frm.doc.channel)) {
			receiver_fields = $.map(fields, function (d) {
				if (frappe.model.table_fields.includes(d.fieldtype)) {
					let child_fields = frappe.get_doc('DocType', d.options).fields
					return $.map(child_fields, function (df) {
						return df.options == 'Email' || (df.options == 'User' && df.fieldtype == 'Link')
							? get_select_options(df, d.fieldname)
							: null
					})
				}
				return d.options == 'Email' || (d.options == 'User' && d.fieldtype == 'Link') ? get_select_options(d) : null
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

frappe.notification.setup_example_message = function (frm) {
	let template = ''
	if (frm.doc.channel === 'Email') {
		template = `<h5>Message Example</h5>

<pre>&lt;h3&gt;Order Overdue&lt;/h3&gt;

&lt;p&gt;Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.&lt;/p&gt;

&lt;!-- show last comment --&gt;
{% if comments %}
Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
{% endif %}

&lt;h4&gt;Details&lt;/h4&gt;

&lt;ul&gt;
&lt;li&gt;Customer: {{ doc.customer }}
&lt;li&gt;Amount: {{ doc.grand_total }}
&lt;/ul&gt;
</pre>
		`
	} else if (MARKDOWN_EXAMPLE_CHANNELS.includes(frm.doc.channel)) {
		template = `<h5>Message Example</h5>

<pre>*Order Overdue*

Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.

<!-- show last comment -->
{% if comments %}
Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
{% endif %}

*Details*

• Customer: {{ doc.customer }}
• Amount: {{ doc.grand_total }}
</pre>`
	}
	if (template) {
		frm.set_df_property('message_examples', 'options', template)
	}
}
