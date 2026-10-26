# Documentation map and translations

**English** | [한국어](../locales/ko/pages/development/documentation.md)

[Documentation home](../README.md)

Keep the documentation home short and place detailed navigation under reader tasks.
Maintain one canonical body per document; several indexes may link to it.

| Location | Contents |
|---|---|
| `getting-started/` | Installation and first-calculation route |
| `modeling/` | Geometry, materials, mesh and package composition |
| `physics/` | EM, heat, electric/Joule and mechanics routes with interfaces, contracts and evidence |
| `results/` | Saved outputs, export and physical trust checks |
| `guide/` | Task-oriented usage routes |
| `reference/` | Package API and JSON contract index |
| `theory/` | Formulation and numerical-method reading routes |
| `validation/` | Independent references, acceptance, benchmarks and historical records |
| `development/` | Contributor entry point and documentation maintenance |
| `packages/<package>/` | Existing canonical package usage, implementation contracts and validation records |

## New pages and translations

1. Update an existing canonical page when the subject belongs there. Put new package documents in `docs/packages/<package>/`.
2. Maintain a Korean counterpart at the same relative path under `docs/locales/ko/pages/`. The English home `docs/README.md` corresponds to Korean `index.md`.
3. Link from the relevant indexes in both languages and add reciprocal language links. Preserve units, equations, commands, thresholds, sources, dates and limits.
4. Distinguish teaching, normative contracts, measurements and historical records. An index must not invent new theory or validation results.

Keep established package paths for citations and inbound links. If a separate change
moves a canonical body, update relative links, images, manifests and code references
together. Public documents cite shipped material or accessible public sources; private
paths and session records stay outside the public repository.

## Check links

From the repository root, stage new files before running these commands: the checker
reads tracked Markdown only.

```sh
python tools/check_markdown_links.py
python -m pytest -q tools/tests/test_markdown_links.py tools/tests/test_readme_links.py
```

These checks do not fetch external URLs or validate physics. Follow the
[contribution policy](../contributing.md) and [development and validation guide](../development.md)
for the full review and CI process.


## OpenPhysics navigation axes

Keep model→physics→execution→results as the primary route. Physics pages distinguish
Python engines, JSON/CLI and Studio, exposing same-mesh, coupling-direction, unit and
boundary restrictions. Package navigation is a separate axis for imports/APIs; do not
hide physical explanations behind package names alone. Keep validation records separate
from usage while linking them from the physical problem. For new features, update the
relevant physics/interface routes and bilingual API/evidence links together. Add learning
or design sections when reviewed material exists, not as empty categories.
