# Security Policy

QuotaPilot handles local quota/account observations and can launch an external
coding agent in an explicitly selected working directory. Security and privacy
reports are welcome, especially for:

- credential, token, cookie, or account-identity leakage,
- shell/argument injection or unsafe command execution,
- authorization, confirmation, retry, or escalation bypasses,
- raw task/transcript persistence,
- unsafe provider-data or quota-history exposure.

Use GitHub private vulnerability reporting for this repository when available.
If it is unavailable, open a minimal public issue requesting a private contact
channel. Do not include credentials, private prompts, account data, exploit
payloads, or sensitive logs in a public issue.

Include the affected version/commit, impact, reproduction conditions, and a
sanitized proof of concept where possible. No response or remediation deadline
is promised.

Normal QuotaPilot behavior is local-first, but real execution can modify the
chosen working directory. Use `quotapilot execute ... --dry-run` to inspect a
plan and keep the default confirmation policy unless you have reviewed a more
permissive local policy.
