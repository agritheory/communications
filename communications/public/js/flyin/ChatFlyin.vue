<template>
	<div ref="host" class="communications-chat-flyin-host" />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps<{
	initialRoomId?: string
	referenceDoctype?: string
	referenceName?: string
}>()

const host = ref<HTMLElement | null>(null)

function resolvedInitialRoomId(): string | undefined {
	if (props.initialRoomId) {
		return props.initialRoomId
	}
	if (props.referenceDoctype && props.referenceName) {
		return `Comment:${props.referenceDoctype}:${props.referenceName}`
	}
	return undefined
}

function mountChat() {
	const api = window.communicationsChatFlyin
	if (!api || !host.value) {
		return
	}

	api.mount(host.value, {
		initialRoomId: resolvedInitialRoomId(),
		referenceDoctype: props.referenceDoctype,
		referenceName: props.referenceName,
	})
}

onMounted(() => {
	mountChat()
})

onUnmounted(() => {
	window.communicationsChatFlyin?.unmount()
})

watch(
	() => [props.initialRoomId, props.referenceDoctype, props.referenceName],
	() => mountChat()
)
</script>

<style scoped>
.communications-chat-flyin-host {
	display: flex;
	flex-direction: column;
	height: 100%;
	min-height: 0;
}
</style>
