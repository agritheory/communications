// Copyright (c) 2026, AgriTheory and contributors
// For license information, please see license.txt

import type {} from '../chat/shims-vue.d.ts'

declare global {
	interface Window {
		communicationsChatFlyin?: {
			mount: (element: HTMLElement, props?: Record<string, unknown>) => void
			updateProps: (props: Record<string, unknown>) => void
			unmount: () => void
			slotId: string
		}
		flyin?: {
			refreshBadge?: (slotId: string) => Promise<void>
		}
		frappe: {
			show_alert: (options: { message: string; indicator?: string }) => void
			realtime: {
				on: (event: string, callback: (data: unknown) => void) => void
				off: (event: string, callback?: (data: unknown) => void) => void
			}
		}
	}
}

export {}
