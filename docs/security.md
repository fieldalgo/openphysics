# Security

**English** | [한국어](locales/ko/pages/security.md)

Please report suspected vulnerabilities through GitHub's
[private vulnerability reporting](https://github.com/fieldalgo/openphysics/security/advisories/new).
Do not put exploit details, credentials or confidential models in a public issue.
Include the affected commit or package version, platform, reproduction steps,
expected impact and a minimal example without sensitive data.

OpenPhysics is under active development. Security fixes are developed on
`main`; there is no promised support period for historical package versions.
Numerical validation is documented in the [documentation index](README.md)
and the tested platforms in the [development guide](development.md).

## Browser Studio

`simcase-studio` is a local tool. It binds to loopback (`127.0.0.1`) by default,
has no accounts and no encryption, and is not a multi-user service: do not
expose it to an untrusted network. A non-loopback `--host` prints a warning.

Other web pages open in the same browser can still try to reach the local
server. The server refuses them before any route runs:

- **Host check (DNS rebinding).** A request is served only when its `Host`
  header names `127.0.0.1`, `localhost`, `::1`, the explicit `--host`, or the
  literal address the connection arrived on, with the port the server listens
  on. Anything else gets 403 (a malformed `Host` gets 400). Open Studio at `http://127.0.0.1:<port>` or
  `http://localhost:<port>`.
- **Origin check (cross-site requests).** A POST (or any method other than
  GET, HEAD, OPTIONS) whose `Origin` is not the Studio page's own origin gets
  403. Without `Origin`, a `Referer` from another origin or
  `Sec-Fetch-Site: cross-site`/`same-site` also gets 403. Requests that carry
  none of these headers, such as `curl` or a Python client, are served as before.
  So is an old browser that sends neither `Origin` nor `Sec-Fetch-Site` and
  suppresses `Referer`; current browsers send `Origin` on every POST.
- **Request bodies.** The optical routes (`/api/validate`, `/api/mesh`,
  `/api/run`, `/api/materials/preview`) accept only `Content-Type:
  application/json` (else 415, without echoing the body) of at most 1 MiB
  (else 413). The thermal routes keep their own limits.
- **Optical jobs.** At most 4 optical jobs run at once (more get 429); the
  server keeps the newest 16 finished optical jobs and frees older ones (an
  older job then answers 404, also to the workspace's Resume button). A
  failed job reports its error message; the traceback goes to the server log only.
- **Pages.** Every response from the server's routes and refusals carries a
  Content-Security-Policy: scripts only from
  the server itself plus the one hashed inline script of the classic editor,
  no plugins, no framing (`frame-ancestors 'none'`, `X-Frame-Options: DENY`),
  network requests only to the same origin. Inline styles stay allowed
  (`style-src 'unsafe-inline'`). The classic editor writes document text
  (names, materials, parameters) as text, so a crafted model file cannot inject
  markup. The interactive API pages `/docs` and `/redoc`, which load Swagger UI
  from a CDN, are switched off.

These checks do not depend on the FastAPI version or on the browser's Local
Network Access rules. They do not make Studio safe on a shared or untrusted
network: anyone who can reach the port can run jobs.
