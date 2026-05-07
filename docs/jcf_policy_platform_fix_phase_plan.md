# JCF Policy Platform Fix Phase Plan

Source document: `C:\Users\Sanique Richards\Documents\CASE MANAGEMENT\FNID SKILLS\13432 Cpl. M. Williams workflow\Policy and Reference\JCF Case Management Policy and Standard Operating Procedures 2024-Sept-12.pdf`

## Goal

Bring the FNID case-management platform into end-to-end alignment with the JCF Case Management Policy and Standard Operating Procedures, especially the registry, DCRR, CR forms, case-review workflow, supervisory vetting, court submission, and case-file movement requirements.

The platform should let a Registrar, investigator, supervisor, team lead, and command user move a case from intake through appreciation, vetting, assignment, investigation, review, court preparation, court result, closure, suspension, or cold-case handling while preserving the official Case Reference Number, required CR forms, registers, audit trail, printable records, and editable working copies.

## Policy Anchors

- The DCR is the central case repository and must receive, register, secure, monitor, review, and update case files.
- All reports must be appreciated, recorded in the relevant register, assigned a Case Reference Number, and connected to the correct CR forms.
- Initial investigators and supervisors must complete and vet relevant CR forms before DCR submission, with 48-hour and 72-hour handoff expectations depending on the workflow.
- Case Reference Numbers must appear on related documents and must retain the slash-based policy format.
- Original case files stay secured by the DCR; file movement must be tracked in the Case File Movement Register.
- DCRR entries must support arrest/no-arrest color semantics and cross-reference crime registers.
- Reviews, conferences, tasks, and next-review dates must be reflected on CR2, the DCRR, and the relevant crime register.
- Court submission requires final DCR vetting, CR12, CR13, CR14, CR15 where relevant, and a Case File Submission Register entry at least 48 hours before court.
- Suspended matters must be reviewed every 90 days and remarks must be recorded in the DCRR.
- The correct term is Case Reference Form, not Crime Reference Form.

## Browser Audit Result

Audited locally at `http://127.0.0.1:5001/` using the in-app browser.

| Area | Result | Evidence | Status |
| --- | --- | --- | --- |
| Login and authenticated navigation | Passed | Browser session logged in as `ADMIN`; home and protected routes loaded. | Working locally |
| Case intake | Initially failed with a 500, then passed | `/cases/intake` was missing the `case_numbers` helper in the template context. A browser-created test case now exists: `FNID/SD/A3/FNID/2026/0001`. | Fixed |
| Policy case reference routing | Initially failed with 404 after intake, then passed | Slash-based case IDs such as `FNID/SD/A3/FNID/2026/0001` broke detail and workflow links. | Fixed with path route converters |
| Case detail | Passed after route fix | Detail page loads, showing case status, DCRR number, lifecycle stage, tabs, forms, review, timeline, and quick links. | Working locally |
| CR forms list | Passed | `/cases/FNID/SD/A3/FNID/2026/0001/forms` shows Investigator and Team Lead sections plus official CR form actions. | Working locally |
| CR1 create/edit/save | Passed | Browser filled and saved a CR1 draft with a narrative entry. The saved record appears in Existing CR Forms. | Working locally |
| CR1 print | Passed | Saved CR1 print view renders read-only with the browser audit narrative and official form structure. | Working locally |
| CR1 PDF export | Passed by HTTP route verification | Route returns `application/pdf`; browser treats it as a file response. Download filename is now sanitized so slash-based case IDs do not become path-like filenames. | Fixed |
| Registry page | Initially failed with a 500, then passed | Template used an unsupported Jinja `search` test when cases existed. KPI counts are now calculated in Python. | Fixed |
| Policy forms library | Passed | `/policy/forms` shows official forms, CR10 as Coming Soon, printable views, DOCX downloads, and the register workbook link. | Working locally |
| Registry workbook download | Passed | `/policy/registers/workbook/download` returns an Excel workbook response. | Working locally |
| Case review | Passed | Browser recorded a scheduled preliminary-vetting review and set next review date `2026-08-01`. | Working locally |
| Stage transition | Passed | Browser transitioned the test case from Intake to Appreciation and verified the timeline entry. | Working locally |
| Full policy completion | Partial | Core paths now work, but policy gating, deadline enforcement, DCRR color semantics, CR2 task synchronization, court-submission controls, and register synchronization still need deeper implementation. | Needs phased work |

## Phase 1 - Stabilize Workflow Foundations

Objective: remove route, template, and export defects that prevent users from completing the policy workflow.

Deliverables:
- Keep slash-based Case Reference Numbers working across case detail, timeline, assignment, transition, review, summary, forms, file movement, correspondence, evidence, SOP, witness, disclosure, and workflow routes.
- Add route regression tests for policy-format case numbers.
- Keep `/cases/intake`, `/unit/registry`, `/policy/forms`, and `/cases/<case>/forms` in the smoke-test set.
- Sanitize generated file names while preserving the official displayed Case Reference Number.
- Add consistent error logging for 500s in workflow-critical pages.

Definition of done:
- Browser can create a case, open its detail page, save a CR form, print it, export it, record a review, transition stage, and return to the registry without 404/500 errors.
- Focused pytest suite passes.

## Phase 2 - Align Data Model To Policy

Objective: make the database represent the policy workflow instead of only the visible screens.

Deliverables:
- Add first-class models or normalized fields for DCRR entries, Major Crime Register, Minor Crime Register, Case File Movement Register, Inward/Outward Correspondence Register, Case File Submission Register, review tasks, and court outcomes.
- Add a policy register map that links each workflow event to its required register update.
- Store the DCRR color state or arrest state explicitly.
- Store original-file vs working-copy movement state.
- Add CR10 as unavailable until the authoritative template is supplied, and prevent it from being treated as implemented.
- Add data validation for required case reference, offence, complainant, accused/suspect, OIC, station, parish, register, and review fields.

Definition of done:
- Every policy-required register has a backing data object, a list view, export path, and print path.
- Case intake creates or updates the relevant DCRR/register records atomically.

## Phase 3 - Build Registry Workflow Engine

Objective: turn the platform into a guided registry pipeline.

Deliverables:
- Implement stage-specific gates for intake, appreciation, vetting, assignment, investigation, review, court preparation, court submission, closure, suspension, reopening, and cold-case handling.
- Add required-action checklists for each stage and role.
- Enforce 48-hour, 72-hour, 48-hours-before-court, and 90-day suspended-case review rules with due dates, warnings, and overdue alerts.
- Link all supervisor/team-lead generated tasks to CR2.
- Record review dates on the case, CR2, DCRR, and relevant crime register.
- Add role-specific dashboards for Registrar, Investigator, Supervisor, Team Lead, and Command.

Definition of done:
- Users cannot advance a case without completing the policy-required documents and register updates for that stage, unless an authorized override is recorded.

## Phase 4 - Complete Official Forms And Register Outputs

Objective: make official forms and register outputs trustworthy for editing and printing.

Deliverables:
- Keep uploaded CR1-CR9 and CR11-CR15 templates as exact editable/printable replicas.
- Add authoritative CR10 only when the source template is supplied.
- Make the register workbook sheets editable, printable, and populated from live registry data where appropriate.
- Add print/export tests for blank forms, case-prefilled forms, saved forms, and register sheets.
- Add field-level prefill rules from case data, DCRR data, review tasks, court data, and file movement data.
- Keep all labels using Case Reference Form terminology.

Definition of done:
- An investigator or team lead can open the case, fill the appropriate CR form, save it as draft/submitted, print it, export it, and see it reflected in the workflow and register context.

## Phase 5 - Court Submission And DPP Controls

Objective: make court and DPP preparation match policy requirements.

Deliverables:
- Add a court-preparation gate requiring CR12, CR13, CR14, and CR15 where relevant.
- Add Case File Submission Register creation and receiving-officer fields.
- Require final DCR vetting before court submission.
- Track DPP pipeline status and return-for-action decisions.
- Capture court attendance, adjournments, final results, and DCRR remarks.

Definition of done:
- A case cannot move to court-submitted without the checklist, submission register, profile/remand documents where applicable, and final vetting record.

## Phase 6 - Quality, Audit, And Production Readiness

Objective: make the platform reliable enough for operational use.

Deliverables:
- Add browser-based end-to-end tests for intake-to-review-to-court-prep workflows.
- Add permission tests for Registrar, IO, Supervisor, Team Lead, and Admin roles.
- Add audit-log verification for form saves, PDF exports, transitions, assignments, file movement, and court submissions.
- Add backup/restore documentation for the SQLite database and uploaded/generated documents.
- Add operational health checks for missing templates, missing workbook, failed PDF renderer, and schema drift.

Definition of done:
- The platform has automated tests for the policy-critical paths, clear user-facing errors, and a repeatable deployment/backup runbook.

## Immediate Next Build List

1. Implement Phase 2 register data objects and live registry synchronization.
2. Add CR2 task synchronization from reviews, conferences, vetting, and supervisor directives.
3. Add deadline alerts for 48-hour, 72-hour, court-minus-48-hour, and suspended-case 90-day requirements.
4. Add stage gates for court preparation and closure/suspension.
5. Build a browser test that creates a case, completes required forms, advances stages, records file movement, submits for court, and verifies register outputs.
