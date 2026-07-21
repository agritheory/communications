# Copyright (c) 2025, Avunu LLC
# License: MIT. See LICENSE
"""
Data retrieval functions for the Chat API.

Functions for fetching rooms, messages, and user information.
"""

from datetime import datetime
from typing import Any, Literal, cast

import frappe
from frappe import _
from frappe.query_builder import DocType, Order
from frappe.query_builder.functions import Count, Max
from frappe.utils import cint, get_url

from communications.api.chat.formatting import html_to_plain_text, strip_quoted_replies
from communications.api.chat.helpers import (
	build_room_from_thread,
	get_user_avatar,
	get_user_status,
	parse_room_id,
)
from communications.api.chat.router import is_comment_room
from communications.api.chat.types import (
	CurrentUser,
	Message,
	MessageFile,
	MessagesResponse,
	ReplyMessage,
	Room,
	RoomsResponse,
)


def get_current_user() -> CurrentUser:
	"""
	Get information about the currently logged-in user.

	Returns:
	    CurrentUser dict with user details for vue-advanced-chat
	"""
	user = frappe.session.user

	User = DocType("User")
	result = (
		frappe.qb.from_(User)
		.select(User.name, User.full_name, User.user_image, User.email, User.last_active)
		.where(User.name == user)
		.limit(1)
		.run(as_dict=True)
	)

	if not result:
		frappe.throw(_("User not found"), frappe.DoesNotExistError)

	user_data = result[0]

	return {
		"_id": user_data["name"],
		"username": user_data.get("full_name") or user_data["name"],
		"avatar": get_user_avatar(user_data["name"]),
		"email": user_data.get("email", ""),
		"fullName": user_data.get("full_name") or user_data["name"],
		"status": get_user_status(user_data["name"]),
	}


def get_comment_rooms(page: int = 1, limit: int = 20, search: str = "") -> RoomsResponse:
	"""
	Get list of Channels and documents with comments as conversation rooms.

	Args:
	    page: Page number for pagination (1-indexed)
	    limit: Number of rooms per page
	    search: Search query for filtering rooms

	Returns:
	    RoomsResponse with list of rooms and pagination info
	"""
	page = cint(page) or 1
	limit = cint(limit) or 20
	offset = (page - 1) * limit
	current_user_id = frappe.session.user

	Comment = DocType("Comment")
	Channel = DocType("Channel")

	# First, get all Channels (not archived)
	channel_query = (
		frappe.qb.from_(Channel)
		.select(
			Channel.name,
			Channel.channel_name,
			Channel.modified,
		)
		.where(Channel.is_archived == 0)
	)

	if search:
		tokens = [t.strip() for t in search.split() if t.strip()]
		if tokens:
			for token in tokens:
				tp = f"%{token}%"
				channel_query = channel_query.where((Channel.name.like(tp)) | (Channel.channel_name.like(tp)))

	channels = channel_query.orderby(Channel.modified, order=Order.desc).run(as_dict=True)

	# Subquery to get the latest comment per document
	latest_comment_query = (
		frappe.qb.from_(Comment)
		.select(
			Comment.reference_doctype,
			Comment.reference_name,
			Max(Comment.modified).as_("last_modified"),
		)
		.where(Comment.comment_type == "Comment")
		.where(Comment.reference_doctype.isnotnull())
		.where(Comment.reference_name.isnotnull())
		.groupby(Comment.reference_doctype, Comment.reference_name)
	)

	# Apply search filter if provided
	if search:
		tokens = [t.strip() for t in search.split() if t.strip()]
		if tokens:
			for token in tokens:
				tp = f"%{token}%"
				latest_comment_query = latest_comment_query.having(
					(Comment.reference_doctype.like(tp)) | (Comment.reference_name.like(tp))
				)

	# Get the grouped results (we'll combine with channels later)
	grouped_comments = latest_comment_query.orderby("last_modified", order=Order.desc).run(
		as_dict=True
	)

	# Build list of all reference_doctype:reference_name pairs
	# Use a dict to deduplicate (in case a Channel has comments, it would appear in both lists)
	all_refs_dict = {}

	# Add channels to the dict
	for channel in channels:
		key = f"Channel:{channel['name']}"
		all_refs_dict[key] = {
			"reference_doctype": "Channel",
			"reference_name": channel["name"],
			"last_modified": channel["modified"],
		}

	# Add documents with comments (will update existing Channels with latest comment time)
	for comment_group in grouped_comments:
		key = f"{comment_group['reference_doctype']}:{comment_group['reference_name']}"
		# If it's already in dict (e.g., Channel), use the max of both timestamps
		if key in all_refs_dict:
			existing_time = all_refs_dict[key]["last_modified"]
			new_time = comment_group["last_modified"]
			all_refs_dict[key]["last_modified"] = max(existing_time, new_time)
		else:
			all_refs_dict[key] = comment_group

	# Convert back to list and sort by last_modified
	all_refs = list(all_refs_dict.values())
	all_refs.sort(key=lambda x: x.get("last_modified", ""), reverse=True)

	# Apply pagination
	paginated_refs = all_refs[offset : offset + limit]

	rooms: list[Room] = []

	for group in paginated_refs:
		reference_doctype = group["reference_doctype"]
		reference_name = group["reference_name"]

		# Get the last comment for this document
		last_comment = (
			frappe.qb.from_(Comment)
			.select(
				Comment.name,
				Comment.content,
				Comment.comment_email,
				Comment.modified,
				Comment.seen,
			)
			.where(Comment.reference_doctype == reference_doctype)
			.where(Comment.reference_name == reference_name)
			.where(Comment.comment_type == "Comment")
			.orderby(Comment.modified, order=Order.desc)
			.limit(1)
			.run(as_dict=True)
		)

		if not last_comment:
			continue

		last_comment_data = last_comment[0]

		# Get unread comment count
		unread_count_result = (
			frappe.qb.from_(Comment)
			.select(Count(Comment.name))
			.where(Comment.reference_doctype == reference_doctype)
			.where(Comment.reference_name == reference_name)
			.where(Comment.comment_type == "Comment")
			.where(Comment.seen == 0)
			.run()
		)
		unread_count = unread_count_result[0][0] if unread_count_result else 0

		# Get document title
		doc_title = None

		# Special handling for Channel doctype - use channel_name field
		if reference_doctype == "Channel":
			try:
				doc_title = frappe.db.get_value("Channel", reference_name, "channel_name")
			except Exception:
				pass
		else:
			# For other doctypes, try title field first, then common fields
			try:
				meta = frappe.get_meta(reference_doctype)
				title_field = meta.get_title_field()

				if title_field and title_field != "name":
					# Use the configured title field
					doc_title = frappe.db.get_value(reference_doctype, reference_name, title_field)
				else:
					# Try common title fields
					for field in ["title", "subject", "task_name", "issue_name", "customer_name"]:
						if meta.has_field(field):
							doc_title = frappe.db.get_value(reference_doctype, reference_name, field)
							if doc_title:
								break
			except Exception:
				pass

		# Fall back to name if no title found
		if not doc_title:
			doc_title = reference_name

		# Build room ID
		room_id = f"Comment:{reference_doctype}:{reference_name}"

		# Get sender name for last message
		sender_name = last_comment_data.get("comment_email", "Unknown")
		try:
			sender_full_name = frappe.db.get_value("User", sender_name, "full_name")
			if sender_full_name:
				sender_name = sender_full_name
		except Exception:
			pass

		# Build room name - don't add prefix for Channels
		if reference_doctype == "Channel":
			room_name = doc_title
		else:
			room_name = f"{reference_doctype}: {doc_title}"

		# Create room object
		last_content = last_comment_data.get("content", "")
		last_content_text = html_to_plain_text(last_content)
		last_content_text = strip_quoted_replies(last_content_text)

		room: Room = {
			"roomId": room_id,
			"roomName": room_name,
			"avatar": get_url() + "/assets/frappe/images/default-avatar.png",
			"unreadCount": unread_count,
			"index": last_comment_data.get("modified"),
			"lastMessage": {
				"content": last_content_text,
				"senderId": last_comment_data.get("comment_email", ""),
				"username": sender_name,
				"timestamp": str(last_comment_data.get("modified", "")),
				"seen": bool(last_comment_data.get("seen")),
			},
			"users": [
				{
					"_id": current_user_id,
					"username": frappe.db.get_value("User", current_user_id, "full_name") or current_user_id,
					"avatar": get_user_avatar(current_user_id),
					"status": get_user_status(current_user_id),
				}
			],
			"communicationMedium": "Comment",
			"referenceDoctype": reference_doctype,
			"referenceName": reference_name,
		}

		rooms.append(room)

	has_more = offset + limit < len(all_refs)

	return {"rooms": rooms, "total": len(all_refs), "page": page, "hasMore": has_more}


def get_rooms(
	page: int = 1,
	limit: int = 20,
	search: str = "",
	medium: str = "All",
) -> RoomsResponse:
	"""
	Get list of chat rooms (conversation threads).

	Args:
	    page: Page number for pagination (1-indexed)
	    limit: Number of rooms per page
	    search: Search query for filtering rooms
	    medium: Filter by communication medium (Email, SMS, Comment, All)

	Returns:
	    RoomsResponse with list of rooms and pagination info
	"""
	# Route to comment rooms when Comment filter is selected
	if medium == "Comment":
		return get_comment_rooms(page, limit, search)

	page = cint(page) or 1
	limit = cint(limit) or 20
	offset = (page - 1) * limit
	current_user_id = frappe.session.user

	Communication = DocType("Communication")

	base_query = (
		frappe.qb.from_(Communication)
		.select(
			Communication.name,
			Communication.subject,
			Communication.content,
			Communication.text_content,
			Communication.sender,
			Communication.sender_full_name,
			Communication.recipients,
			Communication.phone_no,
			Communication.communication_medium,
			Communication.communication_date,
			Communication.sent_or_received,
			Communication.seen,
			Communication.reference_doctype,
			Communication.reference_name,
			Communication.status,
			Communication.user,
		)
		.where(Communication.communication_type == "Communication")
		.orderby(Communication.communication_date, order=Order.desc)
	)

	if medium and medium != "All":
		base_query = base_query.where(Communication.communication_medium == medium)

	if search:
		# Fuzzy search: split query into tokens and require each token to
		# match at least one searchable field.  This means "john smith" will
		# match a communication where subject contains "john" AND sender
		# contains "smith", giving a much more flexible search experience.
		tokens = [t.strip() for t in search.split() if t.strip()]

		if tokens:
			# Also look up Contact names linked to Communication via Dynamic Link
			contact_senders: set[str] = set()
			try:
				Contact = DocType("Contact")
				contact_query = frappe.qb.from_(Contact).select(Contact.email_id, Contact.name).distinct()
				# Each token must appear somewhere in the contact name or email
				for token in tokens:
					tp = f"%{token}%"
					contact_query = contact_query.where(
						(Contact.name.like(tp))
						| (Contact.first_name.like(tp))
						| (Contact.last_name.like(tp))
						| (Contact.full_name.like(tp))
						| (Contact.email_id.like(tp))
						| (Contact.company_name.like(tp))
					)
				contact_results = contact_query.run(as_dict=True)
				for c in contact_results:
					if c.get("email_id"):
						contact_senders.add(c["email_id"])
			except Exception:
				# If Contact doctype doesn't exist or query fails, skip
				pass

			for token in tokens:
				tp = f"%{token}%"
				token_conditions = (
					(Communication.subject.like(tp))
					| (Communication.content.like(tp))
					| (Communication.text_content.like(tp))
					| (Communication.sender.like(tp))
					| (Communication.sender_full_name.like(tp))
					| (Communication.recipients.like(tp))
					| (Communication.phone_no.like(tp))
				)

				# If any contacts matched, also include communications from
				# those senders so that searching by contact name works
				if contact_senders:
					sender_conditions = [Communication.sender.like(f"%{s}%") for s in contact_senders]
					sender_criterion = sender_conditions[0]
					for sc in sender_conditions[1:]:
						sender_criterion = sender_criterion | sc
					token_conditions = token_conditions | sender_criterion

				base_query = base_query.where(token_conditions)

	all_comms = base_query.run(as_dict=True)

	# Group into rooms by external party identifier
	room_map: dict[str, dict[str, Any]] = {}

	for comm in all_comms:
		medium_type = comm.get("communication_medium", "Email")

		if medium_type in ("SMS", "Phone"):
			identifier = comm.get("phone_no") or ""
			external_name = None
		else:
			if comm.get("sent_or_received") == "Received":
				identifier = comm.get("sender") or ""
				external_name = comm.get("sender_full_name")
			else:
				recipients = comm.get("recipients") or ""
				identifier = recipients.split(",")[0].strip() if recipients else ""
				external_name = None

		room_id = f"{medium_type}:{identifier}"

		if room_id not in room_map:
			room_map[room_id] = {
				**comm,
				"unread_count": 0,
				"_external_identifier": identifier,
				"_external_name": external_name,
				"_has_unreplied": False,
				"_last_received_status": None,
			}

		# Track unreplied status - a room is "open" if the last received message
		# is not Replied or Closed
		if comm.get("sent_or_received") == "Received":
			status = comm.get("status") or ""
			if not room_map[room_id].get("_last_received_status"):
				room_map[room_id]["_last_received_status"] = status
				if status not in ("Replied", "Closed"):
					room_map[room_id]["_has_unreplied"] = True

		if external_name and not room_map[room_id].get("_external_name"):
			room_map[room_id]["_external_name"] = external_name

		if comm.get("sent_or_received") == "Received" and not comm.get("seen"):
			room_map[room_id]["unread_count"] = room_map[room_id].get("unread_count", 0) + 1

	user_id_str = str(current_user_id or "")
	all_rooms = [build_room_from_thread(thread, user_id_str) for thread in room_map.values()]

	# Sort rooms: unreplied first, then by date (most recent first)
	def get_sort_key(r: Room) -> tuple[int, float]:
		room_data = room_map.get(r.get("roomId", ""), {})
		has_unreplied = 0 if room_data.get("_has_unreplied", False) else 1

		index_val = r.get("index")
		if isinstance(index_val, datetime):
			ts = index_val.timestamp()
		else:
			ts = 0.0

		return (has_unreplied, -ts)

	all_rooms.sort(key=get_sort_key)

	total = len(all_rooms)
	paginated_rooms = all_rooms[offset : offset + limit]

	return {
		"rooms": paginated_rooms,
		"total": total,
		"page": page,
		"hasMore": offset + limit < total,
	}


def get_comment_messages(
	room_id: str,
	page: int = 1,
	limit: int = 50,
	before_id: str = "",
) -> MessagesResponse:
	"""
	Get comment messages for a specific document.

	Args:
	    room_id: The room identifier (format: Comment:doctype:docname)
	    page: Page number for pagination (1-indexed)
	    limit: Number of messages per page
	    before_id: Get messages before this message ID (for infinite scroll)

	Returns:
	    MessagesResponse with list of messages and pagination info
	"""
	# Parse room_id: "Comment:Task:TASK-001"
	parts = room_id.split(":", 2)
	if len(parts) != 3 or parts[0] != "Comment":
		frappe.throw(_("Invalid comment room ID"))

	reference_doctype = parts[1]
	reference_name = parts[2]
	current_user_id = frappe.session.user

	page = cint(page) or 1
	limit = cint(limit) or 50

	Comment = DocType("Comment")

	# Base query for comments on this document
	query = (
		frappe.qb.from_(Comment)
		.select(
			Comment.name,
			Comment.content,
			Comment.comment_email,
			Comment.comment_by,
			Comment.creation,
			Comment.modified,
			Comment.seen,
			Comment.subject,
		)
		.where(Comment.reference_doctype == reference_doctype)
		.where(Comment.reference_name == reference_name)
		.where(Comment.comment_type == "Comment")
		.orderby(Comment.creation, order=Order.asc)
		.limit(limit)
		.offset((page - 1) * limit)
	)

	# Get total count
	count_query = (
		frappe.qb.from_(Comment)
		.select(Count(Comment.name))
		.where(Comment.reference_doctype == reference_doctype)
		.where(Comment.reference_name == reference_name)
		.where(Comment.comment_type == "Comment")
	)

	total_result = count_query.run()
	total = total_result[0][0] if total_result else 0

	all_comments = query.run(as_dict=True)

	# Build message objects
	messages: list[Message] = []
	user_name_cache: dict[str, str] = {}

	def get_user_display_name(user_email: str) -> str:
		if not user_email:
			return "Unknown"
		if user_email in user_name_cache:
			return user_name_cache[user_email]
		try:
			full_name = frappe.db.get_value("User", user_email, "full_name")
			display_name = str(full_name) if full_name else user_email
		except Exception:
			display_name = user_email
		user_name_cache[user_email] = display_name
		return display_name

	for idx, comment in enumerate(all_comments):
		sender_id = str(comment.get("comment_email") or comment.get("comment_by") or "Unknown")
		sender_name = get_user_display_name(sender_id)

		# Convert HTML to plain text, then strip quoted replies
		content = comment.get("content", "")
		text_content = html_to_plain_text(content)
		text_content = strip_quoted_replies(text_content)

		message: Message = {
			"_id": comment["name"],
			"indexId": idx,
			"content": text_content,
			"senderId": sender_id,
			"username": sender_name,
			"avatar": get_user_avatar(sender_id),
			"date": str(comment.get("creation", "")).split(" ")[0] if comment.get("creation") else "",
			"timestamp": str(comment.get("creation", "")),
			"system": False,
			"saved": True,
			"seen": bool(comment.get("seen")),
			"deleted": False,
			"edited": False,
			"failure": False,
			"disableActions": False,
			"disableReactions": True,
			"files": [],
			"communicationMedium": "Comment",
			"referenceDoctype": reference_doctype,
			"referenceName": reference_name,
		}

		messages.append(message)

	# Pagination is already handled in the SQL query
	has_more = (page * limit) < total

	return {
		"messages": messages,
		"total": total,
		"page": page,
		"hasMore": has_more,
	}


def get_messages(
	room_id: str,
	page: int = 1,
	limit: int = 50,
	before_id: str = "",
) -> MessagesResponse:
	"""
	Get messages for a specific room (conversation thread).

	Args:
	    room_id: The room identifier (format: medium:identifier)
	    page: Page number for pagination (1-indexed)
	    limit: Number of messages per page
	    before_id: Get messages before this message ID (for infinite scroll)

	Returns:
	    MessagesResponse with list of messages and pagination info
	"""
	if is_comment_room(room_id):
		return get_comment_messages(room_id, page, limit, before_id)

	page = cint(page) or 1
	limit = cint(limit) or 50
	current_user_id: str = str(frappe.session.user or "")

	room_parts = parse_room_id(room_id)
	medium = room_parts.get("medium")
	identifier = room_parts.get("identifier")

	if not medium or not identifier:
		return {"messages": [], "total": 0, "page": page, "hasMore": False}

	Communication = DocType("Communication")
	File = DocType("File")

	query = (
		frappe.qb.from_(Communication)
		.select(
			Communication.name,
			Communication.subject,
			Communication.content,
			Communication.text_content,
			Communication.sender,
			Communication.sender_full_name,
			Communication.recipients,
			Communication.phone_no,
			Communication.communication_medium,
			Communication.communication_date,
			Communication.sent_or_received,
			Communication.seen,
			Communication.status,
			Communication.delivery_status,
			Communication.reference_doctype,
			Communication.reference_name,
			Communication.has_attachment,
			Communication.in_reply_to,
			Communication.user,
		)
		.where(Communication.communication_type == "Communication")
		.where(Communication.communication_medium == medium)
	)

	if medium in ("SMS", "Phone"):
		query = query.where(Communication.phone_no == identifier)
	else:
		query = query.where(
			(Communication.sender == identifier) | (Communication.recipients.like(f"%{identifier}%"))
		)

	query = query.orderby(Communication.communication_date, order=Order.asc)

	# Get total count
	count_query = (
		frappe.qb.from_(Communication)
		.select(Count(Communication.name))
		.where(Communication.communication_type == "Communication")
		.where(Communication.communication_medium == medium)
	)

	if medium in ("SMS", "Phone"):
		count_query = count_query.where(Communication.phone_no == identifier)
	else:
		count_query = count_query.where(
			(Communication.sender == identifier) | (Communication.recipients.like(f"%{identifier}%"))
		)

	total_result = count_query.run()
	total = total_result[0][0] if total_result else 0

	all_messages = query.run(as_dict=True)

	# Build message objects
	messages: list[Message] = []
	user_name_cache: dict[str, str] = {}

	def get_user_display_name(user_email: str) -> str:
		if not user_email:
			return ""
		if user_email in user_name_cache:
			return user_name_cache[user_email]
		full_name = frappe.db.get_value("User", user_email, "full_name")
		display_name = str(full_name) if full_name else user_email
		user_name_cache[user_email] = display_name
		return display_name

	for idx, comm in enumerate(all_messages):
		if comm.get("sent_or_received") == "Sent":
			sender_id: str = str(comm.get("user") or comm.get("sender") or current_user_id or "")
		else:
			if medium in ("SMS", "Phone"):
				sender_id = str(comm.get("phone_no") or identifier or "")
			else:
				sender_id = str(comm.get("sender") or identifier or "")

		# Get attachments
		files: list[MessageFile] = []
		if comm.get("has_attachment"):
			attachments = (
				frappe.qb.from_(File)
				.select(File.name, File.file_name, File.file_url, File.file_size, File.file_type)
				.where(File.attached_to_doctype == "Communication")
				.where(File.attached_to_name == comm["name"])
				.run(as_dict=True)
			)

			for att in attachments:
				file_ext = (att.get("file_name") or "").split(".")[-1].lower()
				file_type = att.get("file_type") or "application/octet-stream"
				files.append(
					{
						"name": att.get("file_name", "attachment"),
						"type": file_type,
						"extension": file_ext,
						"url": f"{get_url()}{att.get('file_url', '')}",
						"size": att.get("file_size", 0),
					}
				)

		comm_date = comm.get("communication_date")
		date_str = comm_date.strftime("%d %b %Y") if comm_date else ""
		time_str = comm_date.strftime("%-I:%M %p") if comm_date else ""

		# Build message content
		raw_content = comm.get("text_content") or comm.get("content") or ""
		if "<" in raw_content and ">" in raw_content:
			from frappe.utils import strip_html_tags

			raw_content = strip_html_tags(raw_content)

		raw_content = strip_quoted_replies(raw_content)

		# For emails, prepend subject as a header
		subject = comm.get("subject", "")
		if medium == "Email" and subject:
			content = f"**{subject}**\n\n{raw_content}"
		else:
			content = raw_content

		# Handle reply
		reply_message = None
		if comm.get("in_reply_to"):
			reply_comm = (
				frappe.qb.from_(Communication)
				.select(
					Communication.name,
					Communication.content,
					Communication.text_content,
					Communication.sender,
					Communication.sent_or_received,
				)
				.where(Communication.message_id == comm["in_reply_to"])
				.limit(1)
				.run(as_dict=True)
			)

			if reply_comm:
				reply_content = reply_comm[0].get("text_content") or reply_comm[0].get("content") or ""
				if "<" in reply_content and ">" in reply_content:
					from frappe.utils import strip_html_tags

					reply_content = strip_html_tags(reply_content)

				reply_sender = str(reply_comm[0].get("sender") or "")
				if not reply_sender:
					if reply_comm[0].get("sent_or_received") == "Received":
						reply_sender = identifier or ""
					else:
						reply_sender = current_user_id

				reply_message = {
					"_id": reply_comm[0]["name"],
					"content": reply_content[:200],
					"senderId": reply_sender,
				}

		comm_name = str(comm.get("name", ""))

		if comm.get("sent_or_received") == "Sent":
			username = get_user_display_name(sender_id)
		else:
			username = str(comm.get("sender_full_name") or sender_id)

		comm_medium = cast(
			Literal["Email", "SMS", "Phone", "Chat", "Other"],
			str(comm.get("communication_medium", "Email")),
		)
		sent_or_recv = cast(Literal["Sent", "Received"], str(comm.get("sent_or_received", "Received")))

		message: Message = {
			"_id": comm_name,
			"senderId": sender_id,
			"indexId": idx,
			"content": content,
			"username": username,
			"avatar": get_user_avatar(sender_id if "@" in sender_id else None),
			"date": date_str,
			"timestamp": time_str,
			"system": False,
			"saved": True,
			"distributed": comm.get("delivery_status") in ("Sent", "Opened", "Read"),
			"seen": bool(comm.get("seen")),
			"deleted": False,
			"edited": False,
			"failure": comm.get("delivery_status") in ("Bounced", "Error", "Rejected"),
			"disableActions": False,
			"disableReactions": True,
			"files": files if files else [],
			"communicationName": comm_name,
			"communicationMedium": comm_medium,
			"sentOrReceived": sent_or_recv,
			"subject": comm.get("subject"),
			"referenceDoctype": comm.get("reference_doctype"),
			"referenceName": comm.get("reference_name"),
		}

		if reply_message:
			message["replyMessage"] = cast(ReplyMessage, reply_message)

		messages.append(message)

	# Paginate
	start_idx = max(0, len(messages) - (page * limit))
	end_idx = len(messages) - ((page - 1) * limit)
	paginated_messages = messages[start_idx:end_idx]

	return {
		"messages": paginated_messages,
		"total": total,
		"page": page,
		"hasMore": start_idx > 0,
	}


def get_unread_count() -> int:
	"""
	Get total count of unread messages across all rooms (Communications + Comments).

	Returns:
	    Total unread message count
	"""
	Communication = DocType("Communication")
	Comment = DocType("Comment")

	# Count unread Communications
	comm_result = (
		frappe.qb.from_(Communication)
		.select(Count(Communication.name))
		.where(Communication.communication_type == "Communication")
		.where(Communication.sent_or_received == "Received")
		.where(Communication.seen == 0)
		.run()
	)
	comm_count = comm_result[0][0] if comm_result else 0

	# Count unread Comments
	comment_result = (
		frappe.qb.from_(Comment)
		.select(Count(Comment.name))
		.where(Comment.comment_type == "Comment")
		.where(Comment.seen == 0)
		.run()
	)
	comment_count = comment_result[0][0] if comment_result else 0

	return comm_count + comment_count
