# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

app_name = "communications"
app_title = "Communications"
app_publisher = "AgriTheory"
app_description = "Messaging and telephony extensions for Frappe"
app_email = "support@agritheory.dev"
app_license = "mit"

# required_apps = []

# add_to_apps_screen = [
# 	{
# 		"name": "communications",
# 		"logo": "/assets/communications/logo.png",
# 		"title": "communications",
# 		"route": "/communications",
# 		"has_permission": "communications.api.permission.has_app_permission"
# 	}
# ]

# app_include_css = "/assets/communications/css/communications.css"
app_include_js = [
	"communications.bundle.js",
]
app_include_css = ["/assets/communications/css/public_calendar.css"]

web_include_css = "/assets/communications/css/public_calendar.css"
web_include_js = "public_calendar.bundle.js"

# website_theme_scss = "communications/public/scss/website"

# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# page_js = {"page" : "public/js/file.js"}

# doctype_js = {"doctype": "public/js/doctype.js"}
# doctype_list_js = {"doctype": "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype": "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype": "public/js/doctype_calendar.js"}

# app_include_icons = "communications/public/icons.svg"

# home_page = "login"

# role_home_page = {
# 	"Role": "home_page"
# }

# website_generators = ["Web Page"]

jinja = {
	"methods": [
		"communications.communications.notifications.rsvp_confirm_url",
		"communications.communications.notifications.rsvp_decline_url",
		"communications.communications.notifications.rsvp_cancel_url",
	],
}

# before_install = "communications.install.before_install"
after_install = "communications.communications.install.after_install"
after_migrate = "communications.communications.install.after_migrate"

# before_uninstall = "communications.uninstall.before_uninstall"
# after_uninstall = "communications.uninstall.after_uninstall"

# before_app_install = "communications.utils.before_app_install"
# after_app_install = "communications.utils.after_app_install"

# before_app_uninstall = "communications.utils.before_app_uninstall"
# after_app_uninstall = "communications.utils.after_app_uninstall"

# notification_config = "communications.notifications.get_notification_config"

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

override_doctype_class = {
	"Notification": "communications.communications.overrides.notification.CommunicationsNotification",
}

has_permission = {
	"Electronic Signature": "communications.communications.doctype.electronic_signature.electronic_signature.has_electronic_signature_permission",
}

website_route_rules = [
	{"from_route": "/electronic_signature/<name>", "to_route": "electronic_signature/[name]"},
	{"from_route": "/electronic_signature", "to_route": "electronic_signature"},
	{"from_route": "/sign/<name>", "to_route": "electronic_signature/[name]"},
	{"from_route": "/sign", "to_route": "electronic_signature"},
]

doctype_js = {
	"Electronic Signature": "public/js/electronic_signature.js",
}

doc_events = {
	"Event": {
		"validate": "communications.communications.overrides.event.validate",
		"on_update": "communications.communications.overrides.event.on_update",
		"on_trash": "communications.communications.overrides.event.on_trash",
	}
}

scheduler_events = {
	"hourly": ["communications.communications.notifications.send_appointment_reminders"],
}

# before_tests = "communications.install.before_tests"

# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "communications.event.get_events"
# }
#
# override_doctype_dashboards = {
# 	"Task": "communications.task.get_dashboard_data"
# }

# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# ignore_links_on_delete = ["Communication", "ToDo"]

# before_request = ["communications.utils.before_request"]
# after_request = ["communications.utils.after_request"]

# before_job = ["communications.utils.before_job"]
# after_job = ["communications.utils.after_job"]

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# auth_hooks = [
# 	"communications.auth.validate"
# ]

# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
