<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Phone Helpers

<div class="byline">
  Tyler Matteson 2026-06-24
</div>


Communications enhances desk **Data** fields with **options = Phone**: live formatting via **libphonenumber-js**, a call button on the field, and server-side validation helpers. This is not a full telephony integration — the default **`start_phone_call`** handler is a stub sites replace with their own provider.

## Desk behavior

### Bundle loading

Phone UI ships in **`communications.bundle.js`**, registered in `hooks.py` → **`app_include_js`**. After `bench build`, the bundle overrides **`frappe.ui.form.ControlData`** for Phone fields (`public/js/phone.js`).

### PhoneField

When a **Data** field has **Options** = **Phone**, **`PhoneField`** (`public/js/phoneField.js`):

- Wraps the input in an input group with a phone icon **Call** button.
- Formats display values as the user types using **`PhoneFormatter`** (`public/js/phoneFormatter.js`), defaulting to the site country from **`frappe.boot.sysdefaults.country_code`** (fallback `US`).
- Stores values in a normalized form when the field is read via jQuery **`.val()`**.
- Supports extensions (`ext`, `x`, `#`, `;`) and dial-pause characters (`,`, `;`, `#`, `*`) for IVR systems.

### Call button

Clicking **Call** opens a dialog with two actions:

1. **Call with communications** — calls the whitelisted method **`communications.communications.start_phone_call`** with `phone_number`, `doctype`, and `docname`.
2. **Call with Telephone** — opens a `tel:` link in the browser for click-to-dial on supported devices.

## Server API

### `start_phone_call` (stub)

```python
@frappe.whitelist()
def start_phone_call(phone_number, doctype, docname):
    print("starting call with", phone_number, doctype, docname)
```

Replace this implementation (or override the method in your site app) to integrate Twilio, Microsoft Teams Phone, a CTI adapter, or another provider. The desk passes the digit string including extension pauses.

### `validate_phone_number`

**`validate_phone_number(phone_number, throw=False)`** in `communications.communications` applies a North-American-style regex (optional `+1`, area code with or without parentheses, optional extension). Returns `True`/`False`; throws **`InvalidPhoneNumberError`** when `throw=True`.

### `validate_data_fields`

**`validate_data_fields(self)`** is available for DocType **`validate`** hooks. It:

- Validates native **Phone** fieldtypes via Frappe’s **`validate_phone_number_with_country_code`**.
- For **Data** fields with **Options** = **Email**, **Name**, **Phone**, or **URL**, runs the matching Frappe or Communications validator.

Wire it from your DocType controller when you want Communications phone rules on custom **Data** fields.

## Configuration

No Communications settings DocType controls phone helpers — they apply automatically to all desk **Phone** option fields once the app is installed and assets are built.

To customize telephony behavior, override **`start_phone_call`** in your site or vertical app and point users to your provider’s workflow from the call dialog (you may also replace **`PhoneField.makeCall()`** via a client script if the stock dialog is insufficient).

## Related

- [Notification Channels](./notification_channels.md)
