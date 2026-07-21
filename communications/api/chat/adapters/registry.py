# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
"""
Registry of chat room adapters.

Each adapter owns a room_id prefix namespace. The whitelisted API and Vue UI stay
fixed; new protocols add an adapter module and register here.
"""

from communications.api.chat.router import NATIVE_COMMUNICATION_MEDIUMS

ADAPTER_KEYS = ("comment", "communication")

# Prefixes reserved for future adapter modules.
FUTURE_ADAPTER_PREFIXES = ("Signal", "IRC", "Telegram")

SUPPORTED_ROOM_PREFIXES = frozenset(
	NATIVE_COMMUNICATION_MEDIUMS | {"Comment", *FUTURE_ADAPTER_PREFIXES}
)
