// Copyright (c) 2026, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Electronic Signature', {
	onload_post_render(frm) {
		if (['Draft', 'Out for Signature'].includes(frm.doc.status)) {
			add_send_signature_invitations_button(frm)
		}
	},
	refresh(frm) {
		if (['Draft', 'Out for Signature'].includes(frm.doc.status)) {
			add_send_signature_invitations_button(frm)
		}
	},
})

function add_send_signature_invitations_button(frm) {
	frm.page.add_action_item(__('Send signature invitations'), () => {
		if (!frm.doc.signers || !frm.doc.signers.length) {
			frappe.msgprint(__('Add at least one signer first.'))
			return
		}
		frm.doc.signers.forEach(row => {
			const recipient = row.email
			if (!recipient) {
				return
			}
			frappe
				.xcall('communications.communications.signatures.fetch_signature_invitation_email', {
					doc: frm.doc,
					recipient: recipient,
				})
				.then(r => {
					return new frappe.views.CommunicationComposer({
						doc: frm.doc,
						frm: frm,
						subject: r.subject || __('Signature requested'),
						recipients: r.recipients,
						attach_document_print: false,
						message: r.email_message || '',
					})
				})
		})
	})
}
