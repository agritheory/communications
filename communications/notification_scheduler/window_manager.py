# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import datetime
from typing import Any
import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime
import json


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
		config = frappe.get_single("Notification Window Settings").get_config()
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
			config = frappe.get_single("Notification Window Settings").get_config()
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
			cache = frappe.cache()
			expired_windows = []
			now = now_datetime()

			for full_key in cache.get_keys(f"{WindowManager.REDIS_KEY_PREFIX}:*") or []:
				try:
					key = full_key.decode("utf-8") if isinstance(full_key, bytes) else full_key
					if "|" in key:
						key = key.split("|", 1)[1]
					data = cache.get_value(key)
					if not data:
						continue

					window_data = json.loads(data) if isinstance(data, str) else data
					if now > get_datetime(window_data["window_end"]):
						expired_windows.append(window_data)
				except Exception as e:
					frappe.log_error(f"Error processing window {key}: {str(e)}", "Window Manager")
					continue

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
