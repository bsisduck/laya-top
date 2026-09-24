# Security policy

## Supported versions

Security fixes target the latest release and the current `main` branch.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| Unreleased `main` | Yes |

## Reporting a vulnerability

Use [GitHub's private vulnerability reporting](https://github.com/bsisduck/laya-top/security/advisories/new). Include the affected version, operating system, reproduction steps, impact, and any suggested mitigation. Remove usernames, paths, process lists, model prompts, and other private host data unless they are essential to the report.

Do not open a public issue for a vulnerability. If private reporting is temporarily unavailable, open a public issue containing only a request for a private contact channel.

You should receive an acknowledgement within three business days and an initial assessment within seven. Timing for a fix depends on severity and complexity. The maintainer will coordinate disclosure and credit with the reporter.

## Scope

High-value reports include unintended process signalling, PID-reuse or ownership-check bypasses, terminal escape injection, sensitive process-data disclosure, unsafe model artifact handling, and dependency or packaging vulnerabilities with a demonstrated impact on laya-top.
