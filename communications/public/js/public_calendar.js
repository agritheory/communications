// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.provide('public_calendar')

public_calendar.Calendar = class Calendar {
	constructor(wrapper, options) {
		this.wrapper = wrapper
		this.options = options
		this.public_calendar = options.public_calendar || null
		this.method = options.method || 'communications.communications.www.calendar.index.get_events'
		this.mode = options.mode || 'calendar'
		this.slot_duration = options.slot_duration || 30
		this.max_meeting_duration = options.max_meeting_duration || this.slot_duration
		this.buffer_time = options.buffer_time || 0
		this.min_notice_hours = options.min_notice_hours || 0
		this.max_advance_days = options.max_advance_days || 30
		this.working_hours = options.working_hours || {}
		this.events_cache = []
		this.init()
	}

	async init() {
		await this.load_libs()
		this.calculate_time_bounds()
		this.setup_calendar()
		this.bind_selector()
	}

	async load_libs() {
		const assets = [
			'assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
			'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js',
		]
		if (frappe.boot.lang && frappe.boot.lang !== 'en') {
			assets.push('assets/frappe/js/lib/fullcalendar/locale-all.js')
		}
		await frappe.require(assets)
	}

	calculate_time_bounds() {
		let minHour = 24
		let maxHour = 0

		for (const day in this.working_hours) {
			const blocks = this.working_hours[day] || []
			for (const block of blocks) {
				if (block.start) {
					const startHour = parseInt(block.start.split(':')[0], 10)
					minHour = Math.min(minHour, startHour)
				}
				if (block.end) {
					const endHour = parseInt(block.end.split(':')[0], 10)
					maxHour = Math.max(maxHour, endHour)
				}
			}
		}

		// Default to business hours if no working hours defined
		if (minHour === 24) minHour = 9
		if (maxHour === 0) maxHour = 17

		// Add 1 hour buffer
		this.minTime = `${String(Math.max(0, minHour - 1)).padStart(2, '0')}:00:00`
		this.maxTime = `${String(Math.min(24, maxHour + 1)).padStart(2, '0')}:00:00`
	}

	setup_calendar() {
		this.$cal = $('<div class="public-calendar">').appendTo(this.wrapper)

		const cal_options = {
			locale: frappe.boot.lang,
			header: {
				left: 'prev,title,next',
				center: '',
				right: 'today,month,agendaWeek,agendaDay',
			},
			defaultView: 'agendaWeek',
			editable: false,
			selectable: this.mode === 'schedule',
			selectOverlap: false,
			selectHelper: true,
			minTime: this.minTime,
			maxTime: this.maxTime,
			contentHeight: 'auto',
			events: (start, end, timezone, callback) => this.fetch_events(start, end, callback),
			eventRender: (event, element) => {
				element.attr('title', event.title)
			},
			eventClick: event => this.on_event_click(event),
			buttonText: {
				today: __('Today'),
				month: __('Month'),
				week: __('Week'),
				day: __('Day'),
			},
		}

		if (this.mode === 'schedule') {
			cal_options.select = (start, end, jsEvent, view) => {
				// Enforce slot duration
				const enforced_end = moment(start).add(this.slot_duration, 'minutes')

				// Validate slot before showing dialog
				if (!this.is_slot_allowed({ start: start })) {
					frappe.show_alert({ message: __('This time slot is not available'), indicator: 'orange' })
					this.$cal.fullCalendar('unselect')
					return
				}

				this.on_slot_select(start, enforced_end)
				this.$cal.fullCalendar('unselect')
			}
			cal_options.slotDuration = this.format_duration(this.slot_duration)
			cal_options.selectAllow = selectInfo => this.is_slot_allowed(selectInfo)
			cal_options.selectConstraint = {
				start: moment().add(this.min_notice_hours, 'hours').format(),
				end: moment().add(this.max_advance_days, 'days').format(),
			}
		}

		this.$cal.fullCalendar(cal_options)
		this.style_buttons()
	}

	format_duration(minutes) {
		const h = Math.floor(minutes / 60)
		const m = minutes % 60
		return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`
	}

	async fetch_events(start, end, callback) {
		const args = {
			start: moment(start).format('YYYY-MM-DD'),
			end: moment(end).format('YYYY-MM-DD'),
		}
		if (this.public_calendar) {
			args.public_calendar = this.public_calendar
		}
		const r = await frappe.call({
			method: this.method,
			args: args,
		})
		const events = (r.message || []).map(e => this.prepare_event(e))
		this.events_cache = events
		callback(events)
	}

	is_slot_allowed(selectInfo) {
		const start = moment(selectInfo.start)
		const end = moment(start).add(this.slot_duration, 'minutes')

		// Check if in the past
		if (start.isBefore(moment())) {
			console.log('Blocked: in the past')
			return false
		}

		// Check min notice hours
		if (this.min_notice_hours > 0) {
			const earliest_allowed = moment().add(this.min_notice_hours, 'hours')
			if (start.isBefore(earliest_allowed)) {
				console.log('Blocked: min notice hours')
				return false
			}
		}

		// Check max advance days
		if (this.max_advance_days > 0) {
			const latest_allowed = moment().add(this.max_advance_days, 'days')
			if (start.isAfter(latest_allowed)) {
				console.log('Blocked: max advance days')
				return false
			}
		}

		// Check working hours for this day (only if working hours are defined)
		const has_working_hours = Object.keys(this.working_hours).length > 0
		if (has_working_hours) {
			const day_name = start.format('dddd').toLowerCase()
			const day_hours = this.working_hours[day_name] || []

			if (day_hours.length === 0) {
				console.log('Blocked: no working hours for', day_name)
				return false
			}

			const time_str = start.format('HH:mm')
			const end_time_str = end.format('HH:mm')
			const in_working_hours = day_hours.some(block => {
				const block_start = (block.start || '').substring(0, 5)
				const block_end = (block.end || '').substring(0, 5)
				return time_str >= block_start && end_time_str <= block_end
			})

			if (!in_working_hours) {
				console.log('Blocked: outside working hours', time_str, end_time_str, day_hours)
				return false
			}
		}

		// Check buffer time against existing events
		if (this.buffer_time > 0) {
			for (const event of this.events_cache) {
				const event_start = moment(event.start)
				const event_end = moment(event.end || event.start)

				const buffered_start = moment(event_start).subtract(this.buffer_time, 'minutes')
				const buffered_end = moment(event_end).add(this.buffer_time, 'minutes')

				if (start.isBefore(buffered_end) && end.isAfter(buffered_start)) {
					console.log('Blocked: buffer time conflict')
					return false
				}
			}
		}

		return true
	}

	prepare_event(e) {
		const allDay = Boolean(cint(e.all_day))
		const title = e.subject || e.busy_text || this.options.busy_text || 'Unavailable'
		return {
			id: e.name,
			title: title,
			start: e.starts_on || e.start,
			end: e.ends_on || e.end,
			allDay: allDay,
			backgroundColor: '#EBF5FF',
			textColor: '#1D4ED8',
		}
	}

	on_event_click(event) {
		// Read-only - no action
	}

	on_slot_select(start, end) {
		this.show_booking_dialog(start, end)
	}

	show_booking_dialog(start, end) {
		const date_str = moment(start).format('dddd, MMMM D, YYYY')
		const start_time_str = moment(start).format('h:mm A')

		// Build duration options in 15-minute increments
		const duration_options = []
		for (let d = this.slot_duration; d <= this.max_meeting_duration; d += 15) {
			const hours = Math.floor(d / 60)
			const mins = d % 60
			let label
			if (hours > 0 && mins > 0) {
				label = `${hours}h ${mins}m`
			} else if (hours > 0) {
				label = `${hours} hour${hours > 1 ? 's' : ''}`
			} else {
				label = `${mins} minutes`
			}
			duration_options.push(`<option value="${d}">${label}</option>`)
		}

		const show_duration_select = duration_options.length > 1

		// Remove existing dialog if any
		$('.booking-dialog-overlay').remove()

		const dialog_html = `
			<div class="booking-dialog-overlay">
				<div class="booking-dialog">
					<div class="booking-dialog-header">
						<h3>${__('Book Appointment')}</h3>
						<button class="booking-dialog-close">&times;</button>
					</div>
					<div class="booking-dialog-body">
						<div class="booking-time-display">
							<div class="booking-date">${date_str}</div>
							<div class="booking-time">
								<span class="booking-start-time">${start_time_str}</span>
								<span class="booking-time-separator"> – </span>
								<span class="booking-end-time">${moment(start).add(this.slot_duration, 'minutes').format('h:mm A')}</span>
							</div>
						</div>
						${
							show_duration_select
								? `
						<div class="booking-field">
							<label for="booking-duration">${__('Duration')}</label>
							<select id="booking-duration" class="form-control">
								${duration_options.join('')}
							</select>
						</div>
						`
								: ''
						}
						<div class="booking-field">
							<label for="booking-subject">${__('Subject')} <span class="required">*</span></label>
							<input type="text" id="booking-subject" class="form-control" required>
						</div>
						<div class="booking-field">
							<label for="booking-description">${__('Notes')}</label>
							<textarea id="booking-description" class="form-control" rows="3"></textarea>
						</div>
					</div>
					<div class="booking-dialog-footer">
						<button class="btn btn-default booking-dialog-cancel">${__('Cancel')}</button>
						<button class="btn btn-primary booking-dialog-confirm">${__('Confirm')}</button>
					</div>
				</div>
			</div>
		`

		const $dialog = $(dialog_html).appendTo('body')
		const self = this

		// Update end time when duration changes
		$dialog.find('#booking-duration').on('change', function () {
			const duration = cint($(this).val())
			const new_end = moment(start).add(duration, 'minutes')
			$dialog.find('.booking-end-time').text(new_end.format('h:mm A'))
		})

		$dialog.find('.booking-dialog-close, .booking-dialog-cancel').on('click', () => {
			$dialog.remove()
		})

		$dialog.on('click', e => {
			if ($(e.target).hasClass('booking-dialog-overlay')) {
				$dialog.remove()
			}
		})

		$dialog.find('.booking-dialog-confirm').on('click', () => {
			const subject = $dialog.find('#booking-subject').val().trim()
			const description = $dialog.find('#booking-description').val().trim()
			const duration = cint($dialog.find('#booking-duration').val()) || this.slot_duration
			const actual_end = moment(start).add(duration, 'minutes')

			if (!subject) {
				$dialog.find('#booking-subject').focus()
				return
			}

			this.book_slot(start, actual_end, { subject, description }, $dialog)
		})

		$dialog.find('#booking-subject').focus()
	}

	async book_slot(start, end, values, $dialog) {
		try {
			$dialog.find('.booking-dialog-confirm').prop('disabled', true).text(__('Booking...'))

			const r = await frappe.call({
				method: 'communications.communications.www.schedule.index.book_appointment',
				args: {
					public_calendar: this.public_calendar,
					starts_on: moment(start).format('YYYY-MM-DD HH:mm:ss'),
					ends_on: moment(end).format('YYYY-MM-DD HH:mm:ss'),
					subject: values.subject,
					description: values.description || '',
				},
			})

			if (r.message) {
				$dialog.remove()
				frappe.show_alert({ message: __('Appointment booked'), indicator: 'green' })
				this.refresh()
			}
		} catch (e) {
			frappe.show_alert({ message: __('Failed to book appointment'), indicator: 'red' })
			$dialog.find('.booking-dialog-confirm').prop('disabled', false).text(__('Confirm'))
		}
	}

	bind_selector() {
		const select = document.getElementById('calendar-select')
		if (!select) return

		select.addEventListener('change', () => {
			const option = select.selectedOptions[0]
			const route = option.dataset.route

			if (route) {
				window.history.pushState({}, '', `/calendar?name=${route}`)
			} else {
				window.history.pushState({}, '', '/calendar')
			}

			this.public_calendar = select.value || null
			this.refresh()
		})
	}

	style_buttons() {
		this.$cal.find('button.fc-state-default').removeClass('fc-state-default').addClass('btn btn-default')

		const leftArrow = frappe.utils?.icon?.('left') || '&larr;'
		const rightArrow = frappe.utils?.icon?.('right') || '&rarr;'

		this.$cal.find('.fc-prev-button span').attr('class', '').html(leftArrow)
		this.$cal.find('.fc-next-button span').attr('class', '').html(rightArrow)
	}

	refresh() {
		this.$cal.fullCalendar('refetchEvents')
	}
}

// Initialization function - extracted for reuse
function initPublicCalendar() {
	const wrapper = document.getElementById('public-calendar-wrapper')
	if (!wrapper) return

	// Prevent double-initialization
	if (wrapper.dataset.initialized) return
	wrapper.dataset.initialized = '1'

	let working_hours = {}
	try {
		working_hours = JSON.parse(wrapper.dataset.workingHours || '{}')
	} catch (e) {}

	const slot_duration = cint(wrapper.dataset.slotDuration) || 30

	new public_calendar.Calendar($(wrapper), {
		public_calendar: wrapper.dataset.calendar || null,
		method: wrapper.dataset.method,
		busy_text: wrapper.dataset.busyText || 'Unavailable',
		mode: wrapper.dataset.mode || 'calendar',
		slot_duration: slot_duration,
		max_meeting_duration: cint(wrapper.dataset.maxDuration) || slot_duration,
		buffer_time: cint(wrapper.dataset.bufferTime) || 0,
		min_notice_hours: cint(wrapper.dataset.minNotice) || 0,
		max_advance_days: cint(wrapper.dataset.maxAdvance) || 30,
		working_hours: working_hours,
	})
}

// Expose init function for explicit calls after SPA navigation
public_calendar.init = initPublicCalendar

// Run on initial full page load
frappe.ready(initPublicCalendar)
