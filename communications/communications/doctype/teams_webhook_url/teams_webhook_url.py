# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TeamsWebhookURL(Document):
	def validate(self):
		if self.use_bot_framework:
			if not (self.bot_app_id and self.tenant_id and self.bot_app_secret):
				frappe.throw("Bot Framework requires Bot App ID, Tenant ID, and Bot App Secret")

	def get_bot_credentials(self):
		"""Get bot credentials for proactive messaging."""
		return {
			"app_id": self.bot_app_id,
			"app_password": self.get_password("bot_app_secret"),
			"tenant_id": self.tenant_id,
			"service_url": self.service_url or "https://smba.trafficmanager.net/teams/",
		}
