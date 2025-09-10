# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt


import requests
from requests.exceptions import HTTPError

import frappe
from frappe.model.document import Document


class TeamsWebhookURL(Document):
	def client(self):
		if not (self.client_id and self.tenant_id and self.client_secret):
			frappe.throw("Graph API credentials required")

		client_secret = self.get_password("client_secret")
		token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

		data = {
			"client_id": self.client_id,
			"client_secret": client_secret,
			"scope": "https://graph.microsoft.com/.default",
			"grant_type": "client_credentials",
		}

		try:
			response = requests.post(token_url, data=data)
			response.raise_for_status()
			token_data = response.json()
			session = requests.Session()
			session.headers.update(
				{
					"Authorization": f"Bearer {token_data['access_token']}",
					"Content-Type": "application/json",
				}
			)
			session.base_url = "https://graph.microsoft.com/v1.0"
			return session

		except HTTPError as e:
			frappe.log_error(
				title="Teams Graph API Authentication Failed",
				message=f"Error obtaining access token: {e.response.text}",
			)
			raise e
