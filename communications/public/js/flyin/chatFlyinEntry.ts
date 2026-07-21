// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

/**
 * Flyin drawer chat bundle.
 *
 * Loaded via app_include_js; the thin ChatFlyin.vue flyin slot shell mounts this
 * app when the drawer opens. Keeps vue-advanced-chat / frappe-ui deps out of
 * the shared flyin.desk.bundle.js build.
 */

import { createApp, h, type App } from 'vue'
import ChatFlyinApp from './ChatFlyinApp.vue'
import 'frappe-ui/style.css'
import 'frappe-ui/editor-style.css'

export interface ChatFlyinMountProps {
	initialRoomId?: string
	referenceDoctype?: string
	referenceName?: string
}

const FLYIN_SLOT_ID = 'communications-chat'

let vueApp: App | null = null
let mountElement: HTMLElement | null = null
let mountProps: ChatFlyinMountProps = {}

function resolveInitialRoomId(props: ChatFlyinMountProps): string | undefined {
	if (props.initialRoomId) {
		return props.initialRoomId
	}
	if (props.referenceDoctype && props.referenceName) {
		return `Comment:${props.referenceDoctype}:${props.referenceName}`
	}
	return undefined
}

function mountChatFlyin(element: HTMLElement, props: ChatFlyinMountProps = {}): void {
	unmountChatFlyin()
	mountElement = element
	mountProps = { ...props }

	const initialRoomId = resolveInitialRoomId(mountProps)

	vueApp = createApp({
		render: () =>
			h(ChatFlyinApp, {
				initialRoomId,
			}),
	})

	vueApp.mount(element)
}

function updateChatFlyinProps(props: ChatFlyinMountProps): void {
	mountProps = { ...mountProps, ...props }
	if (mountElement) {
		mountChatFlyin(mountElement, mountProps)
	}
}

function unmountChatFlyin(): void {
	if (vueApp) {
		vueApp.unmount()
		vueApp = null
	}
}

declare global {
	interface Window {
		communicationsChatFlyin?: {
			mount: typeof mountChatFlyin
			updateProps: typeof updateChatFlyinProps
			unmount: typeof unmountChatFlyin
			slotId: string
		}
	}
}

window.communicationsChatFlyin = {
	mount: mountChatFlyin,
	updateProps: updateChatFlyinProps,
	unmount: unmountChatFlyin,
	slotId: FLYIN_SLOT_ID,
}

export { mountChatFlyin, unmountChatFlyin, updateChatFlyinProps }
