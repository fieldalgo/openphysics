# Security

**English** | [한국어](locales/ko/pages/security.md)

Please report suspected vulnerabilities through GitHub's
[private vulnerability reporting](https://github.com/fieldalgo/openphysics/security/advisories/new).
Do not put exploit details, credentials or confidential models in a public issue.
Include the affected commit or package version, platform, reproduction steps,
expected impact and a minimal example without sensitive data.

OpenPhysics is under active development. Security fixes are developed on
`main`; there is no promised support period for historical package versions.
The browser Studio binds to loopback by default and is intended for local use.
It is not an authenticated multi-user service; do not expose it to an untrusted
network. Numerical validation is documented in the [documentation index](README.md)
and the tested platforms in the [development guide](development.md).
