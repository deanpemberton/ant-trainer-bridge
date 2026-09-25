# Security

## Baseline

This project uses:

- **OWASP SAMM 2.2** for software-assurance governance.
- **OWASP DevSecOps Guideline** for CI/CD controls.
- **OWASP Docker Security Cheat Sheet** for container hardening.

## Implemented controls

- Non-root long-running application process (UID/GID 10001).
- Pinned multi-arch base-image digest.
- Exact runtime Python dependency versions.
- GitHub Actions pinned to immutable commit SHAs.
- SBOM and provenance generation for release images.
- Bandit SAST.
- pip-audit dependency scanning.
- Trivy filesystem, secret and misconfiguration scanning.
- Trivy built-container scanning.
- Weekly scheduled rescans.
- Supervisor-only MQTT credentials; no manual plaintext fallback.
- No trainer-control commands: ANT+ use is passive receive-only.

## Trust boundaries

The Home Assistant App receives raw USB access because libusb must read the ANT receiver. The Python bridge itself runs unprivileged.

The bridge trusts:

1. Home Assistant Supervisor for MQTT connection details.
2. The local ANT USB receiver for ANT network access.
3. ANT+ telemetry only as sensor input.

The bridge does **not** treat ANT telemetry as authorization for security-sensitive actions.

Physical automations such as Training Mode or zone lighting should remain independently opt-in and guarded in Home Assistant.

## Vulnerability reporting

Do not include credentials, Supervisor tokens, MQTT passwords, household network details, or other secrets in public issues.

Security findings are tracked with GitHub Issues. If outside contributors begin reporting vulnerabilities, enable GitHub Private Vulnerability Reporting.

## Updating pinned dependencies

When updating a GitHub Action, base image or Python dependency:

1. Resolve the upstream immutable commit/digest from the authoritative registry/repository.
2. Update the human-readable version comment alongside the pin.
3. Run unit tests and the complete security workflow.
4. Review resulting SBOM/container findings before release.
