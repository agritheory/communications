// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

import { defineConfig } from 'vitest/config'

export default defineConfig({
	test: {
		globals: true,
		environment: 'jsdom',
		coverage: {
			provider: 'v8',
			reporter: ['text', 'json', 'html'],
			exclude: ['node_modules/', 'test/', '*.config.js'],
		},
		include: ['**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
		watchExclude: ['node_modules', 'dist', 'coverage'],
	},
})
