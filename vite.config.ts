// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Icons from 'unplugin-icons/vite'
import path from 'path'
import { existsSync, readFileSync, writeFileSync } from 'fs'

function frappeAssetsPlugin() {
	return {
		name: 'frappe-assets',
		writeBundle(_: unknown, bundle: Record<string, { type?: string; name?: string }>) {
			const sitesDir = path.resolve(__dirname, '../../sites')
			const assetsJsonPath = path.resolve(sitesDir, 'assets', 'assets.json')
			if (!existsSync(assetsJsonPath)) {
				return
			}

			const assetsJson = JSON.parse(readFileSync(assetsJsonPath, 'utf-8'))
			for (const [filename, chunk] of Object.entries(bundle)) {
				if (chunk.type === 'chunk' && chunk.isEntry) {
					assetsJson[`${chunk.name}.bundle.js`] =
						`/assets/communications/dist/${filename}`
				}
				if (chunk.type === 'asset' && filename.endsWith('.css')) {
					assetsJson['chat.flyin.bundle.css'] =
						`/assets/communications/dist/${filename}`
				}
			}
			writeFileSync(assetsJsonPath, JSON.stringify(assetsJson, null, 4))
			console.log('Updated assets.json with chat flyin bundle paths')
		},
	}
}

export default defineConfig({
	plugins: [
		vue({
			template: {
				compilerOptions: {
					isCustomElement: (tag: string) => tag === 'emoji-picker',
				},
			},
		}),
		Icons({
			compiler: 'vue3',
		}),
		frappeAssetsPlugin(),
	],
	build: {
		rollupOptions: {
			input: {
				'chat.flyin': path.resolve(
					__dirname,
					'communications/public/js/flyin/chatFlyinEntry.ts'
				),
			},
			output: {
				entryFileNames: 'js/chat.flyin.bundle.[hash].js',
				assetFileNames: 'css/chat.flyin.bundle.[hash].[ext]',
				format: 'iife',
				name: 'CommunicationsChatFlyin',
				inlineDynamicImports: true,
				exports: 'named',
			},
		},
		outDir: 'communications/public/dist',
		emptyOutDir: false,
		minify: true,
		target: 'es2020',
		sourcemap: true,
		cssCodeSplit: false,
	},
	resolve: {
		extensions: ['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json', '.vue'],
		alias: {
			'@': path.resolve(__dirname, 'communications/public/js'),
			'@vendor-chat': path.resolve(__dirname, 'node_modules/vue-advanced-chat/src'),
			vue: 'vue/dist/vue.esm-bundler.js',
		},
	},
	define: {
		'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'production'),
		__VUE_OPTIONS_API__: true,
		__VUE_PROD_DEVTOOLS__: false,
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
	},
	css: {
		preprocessorOptions: {
			scss: {
				silenceDeprecations: ['import'],
			},
		},
	},
})
