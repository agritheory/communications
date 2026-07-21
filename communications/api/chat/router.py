# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
"""
Room adapter routing for the chat API.

Room IDs use a prefix namespace so new transport adapters (Signal, IRC, Telegram,
etc.) can register without changing the whitelisted API or Vue UI contract.

Examples:
    Comment:Task:TASK-2024-00001  -> comment adapter
    Email:user@example.com        -> communication adapter
    SMS:+15551234567              -> communication adapter
    Signal:thread_abc             -> signal adapter (future)
"""

from typing import Literal

AdapterKey = Literal["comment", "communication"]

NATIVE_COMMUNICATION_MEDIUMS = frozenset({"Email", "SMS", "Phone", "Chat", "Other"})


def adapter_key_for_room(room_id: str) -> str:
	"""Return the adapter key responsible for a room ID."""
	if room_id.startswith("Comment:"):
		return "comment"

	prefix = room_id.split(":", 1)[0]
	if prefix in NATIVE_COMMUNICATION_MEDIUMS:
		return "communication"

	# Future adapters register under their protocol prefix (Signal, IRC, Telegram, …).
	return prefix.lower()


def is_comment_room(room_id: str) -> bool:
	return adapter_key_for_room(room_id) == "comment"


def is_communication_room(room_id: str) -> bool:
	return adapter_key_for_room(room_id) == "communication"
