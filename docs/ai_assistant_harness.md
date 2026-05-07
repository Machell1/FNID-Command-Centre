# Internal AI Work Assistant Harness

This harness adds controlled internal work assistants for FNID platform users. It is designed for operational support, not unattended authority.

## Provider

DeepSeek is called through its OpenAI-compatible chat-completions API when all controls allow it.

Required environment variable:

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
```

Default settings:

- Base URL: `https://api.deepseek.com`
- Model: `deepseek-v4-flash`
- Endpoint: `/chat/completions`
- Output mode: JSON actions

If the API key is missing, the run falls back to a local policy scan and records that no DeepSeek request was made.

## Safety Controls

- Global master switch: `ai_assistants_global_enabled`
- Per-assistant enable switch
- Per-assistant mode: `assistive` or `autonomous`
- Per-assistant approval requirement
- Per-assistant run, action, prompt, and token limits
- Sensitive context switch, off by default
- Action allow-list
- High-risk action block
- Full assistant run and action audit trail
- Human guidance/intervention field on every run
- Non-destructive rollback for applied actions

## Assistant Personas

- Registry Registrar Assistant
- Investigator Work Assistant
- Team Lead Vetting Assistant
- DCR Continuous Vetting Assistant
- Court and DPP Assistant
- Command Oversight Assistant
- AI Safety and Misuse Monitor

## Allowed Action Types

- `create_registry_task`
- `schedule_review`
- `flag_vetting_issue`
- `draft_cr2_directive`
- `draft_case_note`

The harness blocks attempts to delete, close, suspend, submit, share, export, change permissions, use credentials, or communicate outside the platform.

## Human Intervention And Rollback

Humans can intervene from the assistant run page by adding guidance. This pauses the run for review. Applied actions can be rolled back without deleting audit history:

- Registry tasks are marked `Rolled Back`.
- Scheduled reviews are marked `Cancelled`.
- Alerts are dismissed.
- The assistant action remains in the audit chain as `rolled_back`.

## Investigator To Registry Pipeline

The assistant workstation links the IO view to Registry:

1. The Investigator Pipeline shows assigned cases and lets the IO request a controlled assistant scan.
2. The Registry Continuous Vetting Queue lets Registry or supervisors run DCR vetting.
3. Assistant output becomes proposed actions.
4. Registry, supervisors, or command approve/apply tasks.
5. Applied tasking is written to the Investigator Index Card/task pipeline.
