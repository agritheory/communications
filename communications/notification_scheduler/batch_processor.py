# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
from typing import Any
import pytz

import frappe
from frappe.utils import now_datetime

from communications.notification_scheduler.window_manager import WindowManager
from communications.notification_scheduler.dispatcher import Dispatcher
from communications.notification_scheduler.digest_builder import DigestBuilder
from communications.communications.doctype.notification_window_settings.notification_window_settings import (
	NotificationWindowSettings,
)


class DeliveryRestrictions:
	@staticmethod
	def get_current_time_in_timezone(timezone: str) -> datetime:
		try:
			return datetime.now(pytz.timezone(timezone))
		except Exception as e:
			frappe.log_error(f"Error getting time in timezone {timezone}: {str(e)}", "Time Window")
			return now_datetime()

	@staticmethod
	def is_same_window(dt1: datetime, dt2: datetime, window_minutes: int) -> bool:
		try:
			return abs((dt1 - dt2).total_seconds() / 60) <= window_minutes
		except Exception:
			return False

	@staticmethod
	def get_next_delivery_window(timezone: str, start_hour: int, end_hour: int) -> datetime:
		"""Get next available delivery window"""
		try:
			current = DeliveryRestrictions.get_current_time_in_timezone(timezone)
			current_hour = current.hour

			if current_hour < start_hour:
				return current.replace(hour=start_hour, minute=0, second=0, microsecond=0)
			elif current_hour >= end_hour:
				next_day = current + timedelta(days=1)
				return next_day.replace(hour=start_hour, minute=0, second=0, microsecond=0)
			else:
				return current
		except Exception as e:
			frappe.log_error(f"Error getting next delivery window: {str(e)}", "Time Window")
			return now_datetime()

	@staticmethod
	def is_within_delivery_hours(user: str | None = None) -> bool:
		try:
			config = NotificationWindowSettings.get_config()

			if not config.enabled:
				return True

			start_hour = config.delivery_start_hour
			end_hour = config.delivery_end_hour
			timezone = config.time_zone

			if user:
				user_tz = frappe.db.get_value("User", user, "time_zone")
				if user_tz:
					timezone = user_tz

			current = DeliveryRestrictions.get_current_time_in_timezone(timezone)
			current_hour = current.hour

			if start_hour <= end_hour:
				return start_hour <= current_hour < end_hour
			return current_hour >= start_hour or current_hour < end_hour

		except Exception as e:
			frappe.log_error(f"Error checking delivery hours: {str(e)}", "Delivery Restrictions")
			return True

	@staticmethod
	def get_next_delivery_time(user: str | None = None):
		try:
			config = NotificationWindowSettings.get_config()
			timezone = config.time_zone

			if user:
				user_tz = frappe.db.get_value("User", user, "time_zone")
				if user_tz:
					timezone = user_tz

			return DeliveryRestrictions.get_next_delivery_window(
				timezone, config.delivery_start_hour, config.delivery_end_hour
			)

		except Exception as e:
			frappe.log_error(f"Error getting next delivery time: {str(e)}", "Delivery Restrictions")
			return now_datetime()


class BatchProcessor:
	@staticmethod
	def process_expired_windows():
		try:
			for window_data in WindowManager.get_expired_windows():
				try:
					user = window_data["user"]
					window_key = window_data["window_key"]

					notifications = frappe.get_all(
						"Assignment Notification Queue",
						filters={"assigned_to": user, "window_key": window_key, "status": "Queued"},
						fields=[
							"name",
							"bypass_batching",
							"reference_doctype",
							"reference_name",
							"assigned_to",
							"description",
							"assigned_by",
							"assignment_date",
						],
					)

					if not notifications:
						WindowManager.clear_window(user)
						continue

					bypass_notifications = [n for n in notifications if n.bypass_batching]
					batch_notifications = [n for n in notifications if not n.bypass_batching]

					for notification in bypass_notifications:
						try:
							Dispatcher.send_individual_notification(notification["name"])
						except Exception as e:
							frappe.log_error(
								f"Error sending individual notification {notification['name']}: {str(e)}",
								"Batch Processor",
							)

					if batch_notifications:
						if DeliveryRestrictions.is_within_delivery_hours(user):
							BatchProcessor.create_and_send_digest(user, batch_notifications)
							WindowManager.clear_window(user)
						else:
							BatchProcessor.reschedule_notifications(batch_notifications)
							# do NOT clear — reschedule created a new window for this user
					else:
						WindowManager.clear_window(user)

				except Exception as e:
					frappe.log_error(
						f"Error processing window {window_data.get('window_key')}: {str(e)}", "Batch Processor"
					)
					continue

		except Exception as e:
			frappe.log_error(f"Error in process_expired_windows: {str(e)}", "Batch Processor")

	@staticmethod
	def create_and_send_digest(user: str, notifications: list[dict]):
		try:
			config = NotificationWindowSettings.get_config()
			max_size = config.max_digest_size
			chunks = [notifications[i : i + max_size] for i in range(0, len(notifications), max_size)]

			for chunk in chunks:
				for notification in chunk:
					frappe.db.set_value(
						"Assignment Notification Queue", notification["name"], "status", "Processing"
					)

				digest_content = DigestBuilder.build_digest(user, chunk)
				success = Dispatcher.send_digest(user, digest_content, chunk)
				status = "Sent" if success else "Failed"
				for notification in chunk:
					frappe.db.set_value(
						"Assignment Notification Queue",
						notification["name"],
						{"status": status, "processed_at": now_datetime(), "notification_sent": 1 if success else 0},
					)

			frappe.db.commit()

		except Exception as e:
			frappe.log_error(f"Error creating digest for {user}: {str(e)}", "Batch Processor")
			for notification in notifications:
				frappe.db.set_value("Assignment Notification Queue", notification["name"], "status", "Failed")
			frappe.db.commit()

	@staticmethod
	def reschedule_notifications(notifications: list[dict[str, Any]]):
		try:
			grouped: dict[str, list[str]] = {}
			for item in notifications:
				grouped.setdefault(item["assigned_to"], []).append(item["name"])

			for user, names in grouped.items():
				next_start = DeliveryRestrictions.get_next_delivery_time(user)
				new_window_key = WindowManager.schedule_window(user, next_start)
				for name in names:
					frappe.db.set_value(
						"Assignment Notification Queue",
						name,
						{"window_key": new_window_key, "status": "Queued"},
					)

			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Error rescheduling notifications: {str(e)}", "Batch Processor")
