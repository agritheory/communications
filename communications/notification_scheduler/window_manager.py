# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import datetime
from typing import Any
import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime
import json

from communications.communications.doctype.notification_window_settings.notification_window_settings import (
	NotificationWindowSettings,
)


class WindowManager:

	REDIS_KEY_PREFIX = "assignment_notification_window"

	@staticmethod
	def generate_window_key(user: str) -> str:
		window_data = WindowManager.get_window_data(user)
		now = now_datetime()

		if window_data:
			window_start = get_datetime(window_data["window_start"])
			window_end = get_datetime(window_data["window_end"])
			if window_start <= now <= window_end:
				return window_data["window_key"]

		return WindowManager.schedule_window(user, now)

	@staticmethod
	def schedule_window(user: str, start_time) -> str:
		config = NotificationWindowSettings.get_config()
		start = start_time if isinstance(start_time, datetime) else get_datetime(start_time)
		end = add_to_date(start, minutes=config.collection_window_minutes)
		window_key = f"{user}_{start.strftime('%Y%m%d_%H%M%S')}"

		window_data = {
			"window_key": window_key,
			"user": user,
			"window_start": start.isoformat(),
			"window_end": end.isoformat(),
			"notification_count": 0,
		}
		WindowManager.set_window_data(user, window_data)
		return window_key

	@staticmethod
	def get_window_data(user: str) -> dict[str, Any] | None:
		try:
			redis_key = f"{WindowManager.REDIS_KEY_PREFIX}:{user}"
			data = frappe.cache().get_value(redis_key)
			if data:
				return json.loads(data) if isinstance(data, str) else data
		except Exception as e:
			frappe.log_error(f"Error getting window data: {str(e)}", "Window Manager")
		return None

	@staticmethod
	def set_window_data(user: str, data: dict):
		try:
			config = NotificationWindowSettings.get_config()
			redis_key = f"{WindowManager.REDIS_KEY_PREFIX}:{user}"
			frappe.cache().set_value(
				redis_key,
				json.dumps(data, default=str),
				expires_in_sec=(config.collection_window_minutes * 60) + 3600,  # 1 hour buffer
			)
		except Exception as e:
			frappe.log_error(f"Error setting window data: {str(e)}", "Window Manager")

	@staticmethod
	def increment_notification_count(user: str):
		try:
			window_data = WindowManager.get_window_data(user)
			if window_data:
				window_data["notification_count"] = window_data.get("notification_count", 0) + 1
				WindowManager.set_window_data(
					user,
					window_data,
				)
		except Exception as e:
			frappe.log_error(f"Error incrementing count: {str(e)}", "Window Manager")

	@staticmethod
	def get_expired_windows() -> list:
		try:
			now = now_datetime()
			# Query DB for distinct user/window_key pairs that have queued notifications.
			# This avoids fragile Redis key scanning and gracefully handles TTL expiry.
			rows = frappe.get_all(
				"Assignment Notification Queue",
				filters={"status": "Queued"},
				fields=["assigned_to", "window_key"],
			)

			seen_keys: set[tuple] = set()
			expired_windows = []

			for row in rows:
				key = (row.assigned_to, row.window_key)
				if key in seen_keys:
					continue
				seen_keys.add(key)

				data = WindowManager.get_window_data(row.assigned_to)
				if not data:
					# Redis TTL expired before window was processed — treat as expired
					expired_windows.append(
						{"window_key": row.window_key, "user": row.assigned_to, "window_end": now.isoformat()}
					)
					continue

				if get_datetime(data["window_end"]) < now:
					expired_windows.append(data)

			return expired_windows
		except Exception as e:
			frappe.log_error(f"Error getting expired windows: {str(e)}", "Window Manager")
			return []

	@staticmethod
	def clear_window(user: str):
		try:
			redis_key = f"{WindowManager.REDIS_KEY_PREFIX}:{user}"
			frappe.cache().delete_value(redis_key)
		except Exception as e:
			frappe.log_error(f"Error clearing window: {str(e)}", "Window Manager")
