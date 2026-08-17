[English](SECURITY.md) | [简体中文](SECURITY.zh-CN.md)

# Security Policy

## Supported versions

Security fixes target the latest released `0.4.x` line.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the maintainers rather
than opening a public issue. Include a description, reproduction steps and the
affected version.

## Access token handling

Flask-XXLJob uses the official `XXL-JOB-ACCESS-TOKEN` header. The access token:

- is never written to logs;
- never appears in exception messages;
- must never be hard-coded in example projects.

Configure it through `XXL_JOB_ACCESS_TOKEN`, ideally from an environment
variable, and never commit real tokens, internal hostnames or internal IP
addresses.
