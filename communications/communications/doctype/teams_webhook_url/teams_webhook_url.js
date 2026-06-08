// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Teams Webhook URL', {
	refresh: function (frm) {
		load_teams_autocomplete(frm)
	},

	tenant_id: function (frm) {
		load_teams_autocomplete(frm)
	},

	client_id: function (frm) {
		load_teams_autocomplete(frm)
	},

	client_secret: function (frm) {
		load_teams_autocomplete(frm)
	},

	team_id: function (frm) {
		// Auto-fill team name when team ID is selected
		if (frm.teams_data && frm.doc.team_id) {
			let team = frm.teams_data.find(t => t.value === frm.doc.team_id)
			if (team) {
				frm.set_value('team_name', team.description)
			}
		}
	},
})

function load_teams_autocomplete(frm) {
	if (!frm.doc.tenant_id || !frm.doc.client_id || !frm.doc.client_secret) {
		return
	}

	frappe
		.xcall('communications.communications.doctype.teams_webhook_url.teams_webhook_url.get_available_teams', {
			docname: frm.doc.name,
		})
		.then(r => {
			if (r && r.length > 0) {
				frm.teams_data = r
				frm.set_df_property('team_id', 'options', r)
			}
		})
}
