frappe.listview_settings['Assignment Notification Queue'] = {
	get_indicator: function (doc) {
		const status_colors = {
			Queued: 'blue',
			Processing: 'orange',
			Sent: 'green',
			Failed: 'red',
		}
		return [__(doc.status), status_colors[doc.status] || 'gray', 'status,=,' + doc.status]
	},
}
