# Security policy

Hawa is an experimental CFD plugin for Rhino 8 and Grasshopper. It runs inside
Rhino with Rhino's embedded Python runtime and installs pinned Python
dependencies, including PyTorch, on first use. Treat it as research software,
not hardened production software.

## Supported versions

Security fixes go to `main` and the next package built from it. Earlier
pre-releases (0.2, 0.3, 0.4 and frozen release packages) are not patched. Rebuild
or upgrade from `main` instead.

## Reporting a vulnerability

Do not open a public issue, pull request or discussion for a suspected
vulnerability.

Report it privately through GitHub's
[private vulnerability reporting](https://github.com/range-et/hawa-cfd/security/advisories/new)
for this repository. If that is unavailable, contact the maintainer,
[@range-et](https://github.com/range-et), using the contact details on their
GitHub profile, and ask for a private channel before you share details.

Include:

- the affected commit, package version or file;
- the operating system, Rhino version and Hawa backend (CPU, CUDA or MPS);
- steps or a minimal file to reproduce the issue, and the impact you observed;
- whether the issue is already public or being exploited.

Expect an acknowledgement within 7 days. The maintainer will confirm the issue,
agree a fix and disclosure timeline with you, and credit you in the advisory
unless you ask not to be named.

## Scope

In scope:

- code execution or file access triggered by opening a Grasshopper definition,
  Rhino document, case file or result file with Hawa components;
- unsafe handling of downloaded dependencies or bundled packages by the plugin's
  bootstrap and installer (`plugin/Bootstrap.py`, `scripts/build_plugin.py`);
- path traversal or overwriting of user files by export, recording, checkpoint or
  install paths;
- secrets or personal data written into results, manifests, logs or packages.

Out of scope:

- numerical inaccuracy, solver instability or device disagreement. Report these
  as normal GitHub issues; they are tracked through the quality gates;
- vulnerabilities in Rhino, Grasshopper, PyTorch or other third-party
  dependencies themselves. Report those upstream. Tell us if Hawa needs to change
  a pinned version in response;
- vendored upstream code under `vendor/` unless Hawa's changes introduce the
  problem.

## Contributor and agent practices

- Never commit credentials, tokens, private keys or machine-specific secrets.
  Device evidence and manifests must not contain them.
- Keep dependency versions pinned and updated through reviewed pull requests.
- Agents must not print full secret values, change global Git or package-manager
  configuration on a contributor's machine, or bypass authentication. Use the
  provided authenticated tools (for example `gh`) instead.
