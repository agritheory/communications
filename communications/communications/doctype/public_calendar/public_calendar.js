// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Public Calendar', {
	refresh(frm) {
		frm.trigger('render_working_hours')
	},

	render_working_hours(frm) {
		const wrapper = frm.fields_dict.working_hours_editor?.$wrapper
		if (!wrapper) return

		wrapper.empty()

		const hours = frm.doc.working_hours ? JSON.parse(frm.doc.working_hours) : {}
		const weekdays = get_ordered_weekdays()

		const container = $('<div class="working-hours-editor">').appendTo(wrapper)

		for (const day of weekdays) {
			const day_key = day.toLowerCase()
			const blocks = hours[day_key] || []

			const day_row = $(`
				<div class="working-hours-day" data-day="${day_key}">
					<div class="day-label">${day}</div>
					<div class="day-content">
						<div class="day-blocks"></div>
						<button class="btn btn-xs btn-default add-block">
							<svg class="icon icon-sm"><use href="#icon-add"></use></svg>
						</button>
					</div>
				</div>
			`).appendTo(container)

			const blocks_container = day_row.find('.day-blocks')

			if (blocks.length === 0) {
				blocks_container.append('<span class="text-muted closed-label">Closed</span>')
			} else {
				for (let i = 0; i < blocks.length; i++) {
					render_block(frm, blocks_container, day_key, i, blocks[i])
				}
			}
		}

		container.on('click', '.add-block', function () {
			const day = $(this).closest('.working-hours-day').data('day')
			add_block(frm, day)
		})

		container.on('click', '.remove-block', function () {
			const day = $(this).closest('.working-hours-day').data('day')
			const index = $(this).closest('.time-block').data('index')
			remove_block(frm, day, index)
		})
	},
})

function render_block(frm, container, day, index, block) {
	const block_el = $(`
		<div class="time-block" data-index="${index}">
			<input type="time" class="form-control input-sm time-start" value="${block.start || '09:00'}">
			<span class="time-separator">–</span>
			<input type="time" class="form-control input-sm time-end" value="${block.end || '17:00'}">
			<button class="btn btn-xs btn-icon remove-block">
				<svg class="icon icon-sm"><use href="#icon-close"></use></svg>
			</button>
		</div>
	`).appendTo(container)

	block_el.find('.time-start, .time-end').on('change', function () {
		const start = block_el.find('.time-start').val()
		const end = block_el.find('.time-end').val()

		if (start && end) {
			if (start >= end) {
				frappe.show_alert({ message: __('End time must be after start time'), indicator: 'orange' })
				return
			}
			update_block(frm, day, index, start, end)
		}
	})
}

function get_ordered_weekdays() {
	const all_days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
	const start = cint(frappe.sys_defaults.first_day_of_the_week || 0)
	return [...all_days.slice(start), ...all_days.slice(0, start)]
}

function get_working_hours(frm) {
	return frm.doc.working_hours ? JSON.parse(frm.doc.working_hours) : {}
}

function set_working_hours(frm, hours) {
	frm.set_value('working_hours', JSON.stringify(hours))
}

function save_and_rerender(frm, hours) {
	set_working_hours(frm, hours)
	frm.trigger('render_working_hours')
}

function add_block(frm, day) {
	const hours = get_working_hours(frm)
	if (!hours[day]) hours[day] = []
	hours[day].push({ start: '09:00', end: '17:00' })
	hours[day].sort((a, b) => a.start.localeCompare(b.start))
	save_and_rerender(frm, hours)
}

function update_block(frm, day, index, start, end) {
	const hours = get_working_hours(frm)
	if (!hours[day]) hours[day] = []
	hours[day][index] = { start, end }
	set_working_hours(frm, hours)
}

function remove_block(frm, day, index) {
	const hours = get_working_hours(frm)
	if (hours[day]) {
		hours[day].splice(index, 1)
		save_and_rerender(frm, hours)
	}
}
