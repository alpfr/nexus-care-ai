# Architecture Decision Records

Each ADR captures one significant architectural or technical decision with the *why* behind it. ADRs are immutable — when a decision changes, write a new ADR that supersedes the old one.

Use [`0000-template.md`](0000-template.md) as the starting point.

## Index

| # | Title | Status |
|---|---|---|
| 0001 | [Initial stack and architecture](0001-initial-stack-and-architecture.md) | accepted |

## Numbering

Sequential, four digits, no gaps. Pick the next number when you start writing.

## When to write one

You're touching an ADR-worthy decision when any of these are true:

- It's hard to reverse later (database engine, language, deployment topology).
- It affects security or compliance posture.
- Multiple reasonable people would disagree on the call.
- A new contributor would benefit from understanding *why* it was decided.

If you're not sure, write one anyway. ADRs are cheap.
