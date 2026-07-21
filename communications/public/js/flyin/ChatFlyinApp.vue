<template>
	<div class="chat-flyin-root messaging-chat-root">
		<ChatView :initial-room-id="initialRoomId" flyin-mode />
	</div>
</template>

<script setup lang="ts">
import ChatView from '../chat/ChatView.vue'

defineProps<{
	initialRoomId?: string
}>()
</script>

<style>
.chat-flyin-root {
	display: flex;
	flex-direction: column;
	height: 100%;
	min-height: 0;
	overflow: hidden;
}

.chat-flyin-root .chat-container {
	height: 100% !important;
	min-height: 0;
}
</style>
