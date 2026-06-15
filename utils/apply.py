"""Pre-applicant application form helpers.

Section-navigation utilities (_show_section, _wait_for_section, _save_section,
_add_repeater_row, _upload_acf_file) and complete_application_form(), which
fills all 9 sections and submits.

Used by test_tutor_full_application_flow (via import) and the
applicant_credentials session fixture in conftest.py — avoids duplicating
~120 lines of form-filling code.
"""

from datetime import datetime, timedelta

from playwright.sync_api import Page, expect


APPLICATION_URL = "/tutor-section/application/"


def _show_section(page: Page, section_id: str):
    """Activate a section tab pane directly via JS.

    The nav links scroll above the viewport after JS init, so clicking them
    via Playwright times out. We replicate what the click handler does instead:
    strip show/active from all panes, add to target.
    """
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        (function() {{
            document.querySelectorAll('.tab-pane').forEach(function(p) {{
                p.classList.remove('in', 'show', 'active');
            }});
            var target = document.getElementById('{section_id}');
            if (target) {{
                target.classList.add('show', 'active');
                target.scrollIntoView({{block: 'start'}});
            }}
        }})();
    """)
    page.wait_for_selector(f"div#{section_id}.tab-pane.show", timeout=5000)
    page.wait_for_timeout(300)


def _wait_for_section(page: Page, section_id: str) -> None:
    """Wait for a section tab-pane to be visible after a page reload.

    PHP's show_form_location logic does not always resolve to the expected next
    section if the previous section's score hasn't fully propagated before the
    redirect. Falls back to _show_section to force the pane visible via JS.
    """
    try:
        page.wait_for_selector(
            f"div#{section_id}.tab-pane.show", state="visible", timeout=15000
        )
    except Exception:
        _show_section(page, section_id)


def _save_section(page: Page, section_id: str):
    """Click Save & continue inside the specified section's form and wait for reload.

    Must target value='Save & continue' explicitly — most sections also render
    a 'Previous' input[name='formDirection'] that appears first in the DOM.

    Two-phase wait: phase 1 (networkidle) handles ACF's async validation gap;
    phase 2 (wait for section to lose .show) confirms the real POST+redirect
    completed and JS has re-run on the new page.
    """
    form = page.locator(f"div#{section_id} form")
    form.locator("input[name='formDirection'][value='Save & continue']").click()
    page.wait_for_load_state("networkidle", timeout=60000)
    try:
        page.wait_for_selector(
            f"div#{section_id}.tab-pane.show",
            state="hidden",
            timeout=45000,
        )
    except Exception:
        pass


def _add_repeater_row(page: Page, section_id: str, field_name: str) -> "Locator":
    """Add a row to an ACF repeater and return the new row locator."""
    row_sel = f"#{section_id} [data-name='{field_name}'] tr.acf-row:not(.acf-clone)"
    count_before = page.locator(row_sel).count()

    btn = page.locator(
        f"#{section_id} [data-name='{field_name}'] .acf-actions a[data-event='add-row']"
    )
    btn.scroll_into_view_if_needed()
    btn.click(force=True)
    page.wait_for_timeout(800)

    count_after = page.locator(row_sel).count()
    assert count_after > count_before, (
        f"_add_repeater_row: add-row did not increase count for "
        f"{section_id}/{field_name} (before={count_before}, after={count_after})"
    )
    return page.locator(row_sel).last


def _upload_acf_file(page: Page, section_id: str, field_name: str, file_path: str):
    """Upload a file into an ACF file field. Falls back to direct input[type=file]."""
    field_div = page.locator(f"div#{section_id} div[data-name='{field_name}']")

    basic_input = field_div.locator("input[type='file']")
    if basic_input.count() > 0:
        basic_input.set_input_files(file_path)
        page.wait_for_load_state("networkidle", timeout=15000)
        return

    field_div.locator("a[data-name='add'], a.acf-button.button").first.click()
    page.wait_for_selector("div.media-frame", state="visible", timeout=10000)

    upload_tab = page.locator("li.media-menu-item").filter(has_text="Upload Files").first
    if upload_tab.count() > 0:
        upload_tab.click()
        page.wait_for_timeout(300)

    page.locator("div.upload-ui input[type='file']").set_input_files(file_path)
    page.wait_for_load_state("networkidle", timeout=20000)

    select_btn = page.locator(
        "button.media-button-select, button.media-button.media-button-select"
    )
    select_btn.wait_for(state="enabled", timeout=15000)
    select_btn.click()
    page.wait_for_selector("div.media-frame", state="hidden", timeout=10000)


def complete_application_form(page: Page, base_url: str, qts_pdf_path: str):
    """Fill all 9 sections of the pre-applicant application form and submit.

    Preconditions:
      - page is authenticated as a pre-applicant
      - page has been navigated to APPLICATION_URL after registration

    Handles personalDetails → supportingDocuments → teachingExperience →
    delivery → availability → rates → qualifications → references →
    interviewBooking → final submit.

    Returns when #SubmitButton has been clicked and the page has settled.
    The caller can then assert the resulting applicant state.
    """
    # ── personalDetails ───────────────────────────────────────────────────────
    _wait_for_section(page, "personalDetails")
    form = page.locator("form#personalDetailsForm")
    form.locator("div[data-name='first_names'] input").fill("Owl")
    form.locator("div[data-name='last_name'] input").fill("TestApplicant")
    form.locator("div[data-name='preferred_name'] input").fill("Owl")
    form.locator("div[data-name='mobile_phone_number'] input").fill("07700900001")
    form.locator("div[data-name='address'] input").fill("1 Test Street")
    form.locator("div[data-name='town__city'] input").fill("London")
    form.locator("div[data-name='postcode__zip'] input").fill("SW1A 1AA")
    country_sel = form.locator("div[data-name='country'] select")
    if country_sel.count() > 0:
        country_sel.select_option("United Kingdom")
    _save_section(page, "personalDetails")

    # ── supportingDocuments ───────────────────────────────────────────────────
    _wait_for_section(page, "supportingDocuments")
    form = page.locator("form#supportingDocumentsForm")
    form.locator("div[data-name='qts_country'] select").select_option("United Kingdom")
    _upload_acf_file(page, "supportingDocuments", "upload_qts_certificate", qts_pdf_path)
    form.locator(
        "div[data-name='unique_taxpayer_reference_utr_number_country'] select"
    ).select_option("United Kingdom")
    form.locator(
        "div[data-name='sole_trader_or_limited_company'] select"
    ).select_option(index=1)
    confirm_cb = form.locator(
        "div[data-name='confirm_possess_docs'] input[type='checkbox']"
    )
    if confirm_cb.count() > 0 and not confirm_cb.is_checked():
        confirm_cb.check()
    _save_section(page, "supportingDocuments")

    # ── teachingExperience ────────────────────────────────────────────────────
    _wait_for_section(page, "teachingExperience")
    section = page.locator("div#teachingExperience")
    section.locator(
        "div[data-name='years_of_classroom_teaching_experience'] input"
    ).fill("5")
    section.locator(
        "div[data-name='please_describe_your_teaching_experience'] textarea"
    ).fill("Five years teaching secondary Maths in UK state schools. Automated test.")
    mot_cb = section.locator(
        "div[data-name='motivations_for_tutoring'] input[type='checkbox']"
    ).first
    if mot_cb.count() > 0 and not mot_cb.is_checked():
        mot_cb.check()
    row = section.locator(
        "[data-name='please_describe_your_teaching_experience_repeater']"
        " tr.acf-row:not(.acf-clone)"
    ).first
    row.locator("div[data-name='school_name'] input").fill("Owl Test School")
    row.locator("div[data-name='roles'] input").fill("Maths Teacher")
    page.evaluate("""
        (function() {
            var row = document.querySelector(
                '#teachingExperience [data-name="please_describe_your_teaching_experience_repeater"]'
                + ' tr.acf-row:not(.acf-clone)'
            );
            if (!row) return;
            var sh = row.querySelector('[data-name="start_date"] input[type="hidden"]');
            var st = row.querySelector('[data-name="start_date"] input.input');
            var eh = row.querySelector('[data-name="end_date"] input[type="hidden"]');
            var et = row.querySelector('[data-name="end_date"] input.input');
            if (sh) sh.value = '20180901';
            if (st) st.value = '01/09/2018';
            if (eh) eh.value = '20230701';
            if (et) et.value = '01/07/2023';
        })();
    """)
    maths_cb = section.locator(
        "div[data-name='subject_list'] input[type='checkbox'][value='Maths']"
    )
    if maths_cb.count() > 0:
        maths_cb.first.check(timeout=5000)
    _save_section(page, "teachingExperience")

    # ── delivery ──────────────────────────────────────────────────────────────
    _wait_for_section(page, "delivery")
    page.locator(
        "div#delivery div[data-name='delivery'] input[type='checkbox'][value='Online']"
    ).check()
    _save_section(page, "delivery")

    # ── availability ──────────────────────────────────────────────────────────
    _wait_for_section(page, "availability")
    page.locator("div#availability").locator(
        "[data-name='for_how_many_years_do_you_plan_on_being_a_tutor'] input"
    ).fill("3")
    page.wait_for_selector("#tutor_availability_holder", state="attached", timeout=10000)
    page.evaluate(
        "() => new Promise((resolve, reject) => {"
        "    const avail = window.TutorAvail || {};"
        "    const fd = new FormData();"
        "    fd.append('action', 'tutor_availability_save');"
        "    fd.append('nonce', avail.nonce || '');"
        "    fd.append('tutor_id', String(avail.tutorId || ''));"
        "    fd.append('slots', JSON.stringify({'0': [16]}));"
        "    fd.append('extra_capacity', '0');"
        "    fd.append('timezone', 'Europe/London');"
        "    fd.append('notes', '');"
        "    fd.append('date_free', '');"
        "    fetch(avail.ajaxUrl || '/wp-admin/admin-ajax.php', { method: 'POST', body: fd })"
        "        .then(r => r.json())"
        "        .then(data => data.success ? resolve(data) : reject(data))"
        "        .catch(reject);"
        "})"
    )
    page.wait_for_timeout(300)
    _save_section(page, "availability")

    # ── rates ─────────────────────────────────────────────────────────────────
    _wait_for_section(page, "rates")
    rates = page.locator("div#rates")
    rates.locator("div[data-name='minimum_net_home_pay_rate'] select").select_option("30")
    rates.locator("div[data-name='minimum_net_online_pay_rate'] select").select_option("30")
    _save_section(page, "rates")

    # ── qualifications ────────────────────────────────────────────────────────
    _wait_for_section(page, "qualifications")
    quals = page.locator("div#qualifications")
    quals.locator(
        "div[data-name='in_which_subject_did_you_qualify_to_teach'] select"
    ).select_option("Maths")
    quals.locator(
        "div[data-name='what_is_the_name_of_your_teaching_qualification'] input"
    ).fill("PGCE")
    quals.locator(
        "div[data-name='what_is_the_name_of_the_awarding_body_of_your_teaching_qualification'] input"
    ).fill("University College London")
    quals.locator(
        "div[data-name='in_what_year_did_you_achieve_your_teaching_qualification'] input"
    ).fill("2018")
    _save_section(page, "qualifications")

    # ── references ────────────────────────────────────────────────────────────
    _wait_for_section(page, "references")
    lm_row = page.locator(
        "#references [data-name='line_manager_reference'] tr.acf-row:not(.acf-clone)"
    ).first
    lm_row.locator("div[data-name='name_of_school'] input").fill("Owl Test School")
    lm_row.locator("div[data-name='school_address'] input").fill("1 Test Street, London")
    lm_row.locator("div[data-name='first_name'] input").fill("Jane")
    lm_row.locator("div[data-name='last_name'] input").fill("Manager")
    lm_row.locator("div[data-name='relation_to_you'] input").fill("Head of Department")
    lm_row.locator("div[data-name='email_address'] input").fill("manager@owltest.co.uk")
    page.evaluate("""
        (function() {
            var row = document.querySelector(
                '#references [data-name="line_manager_reference"] tr.acf-row:not(.acf-clone)'
            );
            if (!row) return;
            var sh = row.querySelector('[data-name="employment_start_date"] input[type="hidden"]');
            var st = row.querySelector('[data-name="employment_start_date"] input.input');
            var eh = row.querySelector('[data-name="employment_finish_date"] input[type="hidden"]');
            var et = row.querySelector('[data-name="employment_finish_date"] input.input');
            if (sh) sh.value = '20180901';
            if (st) st.value = '01/09/2018';
            if (eh) eh.value = '20230701';
            if (et) et.value = '01/07/2023';
        })();
    """)
    for sel, data in [
        ("#references [data-name='referees2'] tr.acf-row[data-id='row-0']",
         ("John", "Referee", "Former colleague", "referee1@owltest.co.uk")),
        ("#references [data-name='referees2'] tr.acf-row[data-id='row-1']",
         ("Jane", "Referee2", "Former colleague", "referee2@owltest.co.uk")),
    ]:
        row = page.locator(sel)
        row.locator("div[data-name='first_name'] input").fill(data[0])
        row.locator("div[data-name='last_name'] input").fill(data[1])
        row.locator("div[data-name='relation_to_you'] input").fill(data[2])
        row.locator("div[data-name='email_address'] input").fill(data[3])
    _save_section(page, "references")

    # ── interviewBooking ──────────────────────────────────────────────────────
    _wait_for_section(page, "interviewBooking")
    d1 = datetime.now() + timedelta(days=14)
    d2 = datetime.now() + timedelta(days=15)
    d3 = datetime.now() + timedelta(days=16)
    page.evaluate(
        """(dates) => {
            ['first_interview_preference', 'second_interview_preference',
             'third_interview_preference'].forEach((name, i) => {
                const wrap = document.querySelector('[data-name="' + name + '"]');
                if (!wrap) return;
                const h = wrap.querySelector('input[type="hidden"]');
                const d = wrap.querySelector('input.input');
                if (h) h.value = dates[i][0];
                if (d) d.value = dates[i][1];
            });
        }""",
        [
            [d1.strftime("%Y-%m-%d 10:00:00"), d1.strftime("%d/%m/%y 10:00 AM")],
            [d2.strftime("%Y-%m-%d 10:00:00"), d2.strftime("%d/%m/%y 10:00 AM")],
            [d3.strftime("%Y-%m-%d 10:00:00"), d3.strftime("%d/%m/%y 10:00 AM")],
        ]
    )
    _save_section(page, "interviewBooking")

    # ── submit ────────────────────────────────────────────────────────────────
    # Reload fresh so PHP recalculates overall_score from stored meta before
    # we check for #isappreadyForm.
    page.goto(f"{base_url}{APPLICATION_URL}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")

    submit_form = page.locator("form#isappreadyForm")
    expect(submit_form).to_be_visible(timeout=5000)

    submit_form.locator(
        "div[data-name='how_did_you_hear_about_owl_tutors'] input[type='checkbox']"
    ).first.check()
    page.wait_for_timeout(600)
    for inp in submit_form.locator("input[type='text']").all():
        if inp.is_visible():
            inp.fill("Automated test")
            break

    # ACF's JS intercepts the submit button click and runs client-side validation
    # (class="acf-form"), calling preventDefault() — so clicking #SubmitButton
    # never causes a page navigation. Submitting the form directly via JS bypasses
    # ACF's client-side validation while still including all hidden fields in the
    # POST (nonce, acf[is_your_application_ready]=1, etc.), so the PHP promotion
    # hook (acf/save_post priority 20) runs and promotes the user.
    with page.expect_navigation(timeout=15000):
        page.evaluate("document.getElementById('isappreadyForm').submit()")
    page.wait_for_load_state("networkidle", timeout=30000)

    # ACF redirects to 'return' => 'thanks', landing on /tutor-section/application/thanks/.
    # Navigate back to the application page so callers can assert the post-promotion state.
    page.goto(f"{base_url}{APPLICATION_URL}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=30000)
