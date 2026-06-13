<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Electronic Signature and desk connections

<div class="byline">
  Heather Kusmierz and Tyler Matteson 2026-06-13
</div>


**Electronic Signature** can reference any document via **Reference DocType** and **Reference Name** (a Dynamic Link). The Communications app does **not** ship hard-coded links from specific doctypes (for example **Task**) to **Electronic Signature**, because each site chooses which business objects participate in signing.

## Recommended: Document Links (customization)

Add a **Document Link** on each doctype where users should see related signatures in the **Connections** tab.

1. Open **Customize Form** (or **DocType** → **Task**, if you customize in developer mode).
2. Select the target DocType (e.g. **Task**).
3. In **Document Links**, add a row:
   - **Link DocType**: `Electronic Signature`
   - **Link Fieldname**: `reference_name` (this is the Dynamic Link field on **Electronic Signature**)
   - **Group**: any label you want in the connections sidebar (e.g. `Signatures`)
4. Export customizations to your app (with **Export Customization** / `sync_on_migrate`) so the link is version-controlled.

If your bench cannot sync a `links` row from JSON (for example validation differences), add the Document Link once in **Customize Form** and re-export so the file includes the generated **`name`** and any **`links_order`** property setter Frappe creates.

### Dynamic Link caveat

Document Links drive the **Connections** UI and set the dashboard’s `non_standard_fieldnames`. For a **Dynamic Link**, connection **counts** in the desk are most accurate when the dashboard also knows which doctype the reference points to (`reference_doctype` for **Electronic Signature**). Frappe’s `DocType Link` rows do **not** configure that `dynamic_links` map.

In practice:

- If **Reference Name** values are unique per referenced doctype (typical for ERPNext naming), filtering by `reference_name` alone is often enough.
- If you need guaranteed-correct filters or counts, use one of the alternatives below.

## Alternative A: dedicated Link field (customization)

Add a **Link** field on **Electronic Signature** that points at the doctype you care about (e.g. **Link** to **Task** named `task`). Keep it in sync with **Reference DocType** / **Reference Name** via client script, workflow, or server script as needed.

Then add a **Document Link** on **Task** using **`link_fieldname` = `task`** (the static Link field). Dashboard filtering uses a single field and stays correct without extra Python.

## Alternative B: dashboard hook (code)

For a site that wants to keep only the Dynamic Link fields and still set `dynamic_links`, extend **`override_doctype_dashboards`** for the parent doctype—for example merge into the dict returned for **Task**:

- `non_standard_fieldnames["Electronic Signature"] = "reference_name"`
- `dynamic_links["reference_name"] = ["Task", "reference_doctype"]`

This is optional and belongs in the customer or vertical app (not Communications).

## Related

- [Desk integrations (notifications, etc.)](./integrations.md)

## Email Signature Invitations and Portal Access Configuration

A "Send for Signatures" action is available when the Electronic Signature document is in "Draft" or "Out for Signatures" status. This action creates an email composer for each signer in the Signatures table. The composer expects an Email Template to exist with the name "Electronic Signature Request", which is created on installation of the Communications app and may be edited as-needed.

The email body can include a one-time login magic link for the user to directly access the document in the email body. First, "Login with Email Link" must be enabled in System Settings. Second, the "MAGIC_LINK" text must be present in the body of the "Electronic Signature Request" Email Template for the functionality to work. For the link to land on the signing page after login, the site must honor the `redirect-to` query parameter on the login-key handler. Frappe core may not apply that redirect; one option to implement this is by overriding `frappe.www.login.login_via_key`.

At this point, the document should be set to "Out for Signatures" status, as a portal user won't be able to see a document in "Draft" status. From here, they can view and execute the document, as rendered by the print format.

To have a dedicated menu item in the Portal sidebar for users to see the "Sign" endpoint, that may be added in "Portal Settings" in the "Custom Sidebar Menu" table.

Once all users in the Signatures section have executed the document, the status automatically changes to "Completed".
