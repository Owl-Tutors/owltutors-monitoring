from playwright.sync_api import Page, expect


def submit_student_name_if_shown(page: Page, name: str = "Test Student"):
    """
    ot_timesheets_tutor_create_edit() (timesheet-mgmt.php) shows a one-field
    "student name" form first if the job has no student_id set — a real POST
    form (not AJAX), reloading the page. No-op if the goal wizard or timesheet
    form is already showing instead (student_id already set, e.g. a job
    created via the real contact form).
    """
    name_input = page.locator("#student_name")
    if name_input.count() and name_input.is_visible():
        name_input.fill(name)
        page.locator("button[name='save_student_name']").click()
        page.wait_for_load_state("domcontentloaded")


def complete_goal_wizard_via_skip(page: Page):
    """
    Drives the goal-setting wizard (ot_tutor_goal_wizard_handler AJAX action,
    ot_timesheets.js) from step 2 ("Enter goal text") through to the timesheet
    form, using the "Skip" link at each step rather than "Save and next".

    This deliberately avoids ever submitting real goal text: step 2's
    "Save and next" queries ChatGPT to validate the goal against SMART
    criteria (ot_openai_api_call() in timesheet-mgmt.php) — an external,
    non-deterministic dependency with no place in an automated test. The
    "Skip" link takes a different server-side path (the "handle skips" block
    at the top of the handler, checked *before* the step switch) that never
    reaches that call at all.

    Skip path: step 2 -> step 3 ("Use suggested goal?", empty since skipped)
    -> click "Keep my goal" (answer=no, saves an empty-text goal row) -> step
    4 ("target completion date?") -> click "No" -> jumps straight to step 6
    (skips step 5's date entry) -> "Save and next" (likelihood already
    defaults to "Unsure") -> step 7 -> fill the explanation textarea -> click
    "Finish" -> reveals the timesheet form.

    Assumes the wizard is currently showing step 2 (the case whenever a job
    has no goal_repeater yet — ot_timesheets_tutor_create_edit()'s default).

    Scoped to #timesheet: single-jobs.php's "Job details" tab pane also embeds
    a goal form (read-only recap), so an unscoped .goal_form_wrapper locator
    matches two elements (both tab panes stay in the DOM — Bootstrap tabs only
    toggle visibility) and trips Playwright's strict-mode check.
    """
    wrapper = page.locator("#timesheet .goal_form_wrapper")
    expect(wrapper.locator(".goal-step[data-step='2']")).to_be_visible(timeout=10000)

    # Step 2 -> 3: Skip (never calls the AI goal-quality check)
    wrapper.locator(".goal-step[data-step='2'] a.goal-form-btn[data-answer='skip']").click()
    expect(wrapper.locator(".goal-step[data-step='3']")).to_be_visible(timeout=10000)

    # Step 3 -> 4: "Keep my goal" (previousGoal is empty since step 2 was skipped)
    wrapper.locator(".goal-step[data-step='3'] button.goal-form-btn[data-answer='no']").click()
    expect(wrapper.locator(".goal-step[data-step='4']")).to_be_visible(timeout=10000)

    # Step 4 -> 6: "No" target completion date (server jumps straight to step 6)
    wrapper.locator(".goal-step[data-step='4'] button.goal-form-btn[data-answer='no']").click()
    expect(wrapper.locator(".goal-step[data-step='6']")).to_be_visible(timeout=10000)

    # Step 6 -> 7: likelihood select already defaults to "Unsure" — just advance
    wrapper.locator(".goal-step[data-step='6'] button.goal-form-btn-next").click()
    expect(wrapper.locator(".goal-step[data-step='7']")).to_be_visible(timeout=10000)

    # Step 7 -> timesheet form: explanation is required
    wrapper.locator(".goal-step[data-step='7'] textarea.goal_likelihood_explanation").fill(
        "Automated test — unsure, no data yet."
    )
    wrapper.locator(".goal-step[data-step='7'] button.goal-form-btn-next").click()
    expect(page.locator("#tutor_submit_timesheet_form")).to_be_visible(timeout=10000)


def fill_and_submit_timesheet_form(page: Page, submit_type: str = "submit_for_invoicing"):
    """
    Fills the final timesheet form (ot_timesheets_tutor_form_content()) —
    month/year and session 1's start/end datetime are already pre-filled with
    sensible defaults, so only the two free-text fields need real content —
    and submits it. This is a real POST (not AJAX); the server redirects to
    /dashboard/tutoring-section#submit_a_timesheet on success.

    The "submit_for_invoicing" path (handleTimesheetButtons in ot_timesheets.js)
    shows a native confirm() before submitting — Playwright auto-dismisses
    unhandled dialogs, which reads as Cancel and silently no-ops the submit
    (form.submit() is never reached), so the page just sits there until
    wait_for_url times out. Register a one-shot handler that accepts it.

    That same path also calls enforceEbTextareas(true), which sets
    minlength="100" on #monthly_report/#to_improve before form.reportValidity()
    — text shorter than 100 chars fails validation silently (no dialog, no
    server round-trip, just a stuck page), so both fields need >=100 chars.
    """
    if submit_type == "submit_for_invoicing":
        page.once("dialog", lambda dialog: dialog.accept())

    form = page.locator("#tutor_submit_timesheet_form")
    form.locator("#monthly_report").fill(
        "Automated test — covered chapters 1-2, good progress overall this month, "
        "engaged well with the material and completed all set homework tasks."
    )
    form.locator("#to_improve").fill(
        "Automated test — practice past papers before the next session, focusing "
        "on timing and accuracy under exam conditions to build confidence."
    )
    form.locator(f"button[name='save_timesheet'][value='{submit_type}']").click()
