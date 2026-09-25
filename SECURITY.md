# Security

## Security baseline

This project uses the following baseline:

- **OWASP SAMM 2.2** for software-assurance governance and incremental maturity.
- **OWASP DevSecOps Guideline** for CI/CD security activities.
- **OWASP Docker Security Cheat Sheet** for container hardening.

The automated security pipeline currently covers:

- Python SAST with Bandit.
- Python dependency/SCA scanning with pip-audit.
- Filesystem, secret and configuration scanning with Trivy.
- Built container vulnerability scanning with Trivy.
- Weekly scheduled rescans so newly disclosed dependency/base-image CVEs are detected even when source code has not changed.

## Reporting a vulnerability

Do not include credentials, access tokens, private MQTT details, Home Assistant Supervisor tokens, or other household secrets in an issue.

For now, security findings are tracked as GitHub Issues in this repository. If the project becomes public, enable GitHub Private Vulnerability Reporting before inviting external security reports.

## Security assumptions

- MQTT is normally supplied by Home Assistant Supervisor and remains on the internal Home Assistant network.
- The bridge is a passive ANT+ listener and must not issue FE-C trainer-control commands.
- Zone lighting and other physical automation are opt-in and are not part of the ANT receiver trust boundary.
- Raw USB access is security-sensitive and should be constrained as far as Home Assistant App packaging permits.
