# Security boundaries

Author: Armando Gomez

This portfolio uses local stdio MCP sessions. The configured role belongs to a process; it is not internet-facing user authentication. Keep credentials in ignored local configuration. Telegram remains dry-run unless explicitly configured for authorized sends. The published dashboard uses synthetic examples and generated evaluation summaries.

The server filters tools by role and rechecks scope on calls, parameterizes SQLite queries, bounds connector outputs and returns structured errors. Tests include secret-leak checks and untrusted-content handling. These controls are not a sandbox against a malicious local process or a production certification. Raw operational data and screenshots still require private handling.

Main requires a pull request, passing server/eval checks on both operating systems, dependency auditing, and resolved conversations. Administrator enforcement is enabled; force pushes and branch deletion are disabled. The solo-owner policy does not require an additional approving reviewer. GitHub secret scanning, push protection, vulnerability alerts and automatic security fixes are enabled. Dependency updates are not automatically merged.

Actions are pinned to commits, checkout credentials are not retained, and CI uses read-only permissions except the Pages deployment job's narrowly scoped deployment permissions. Weekly Dependabot covers Actions and both Python project manifests. The dependency workflow audits both frozen lockfiles on PR/push and weekly after merge.

From either project directory, reproduce the dependency audit (the output filename below is temporary and must not be committed):

```powershell
uv export --frozen --no-emit-project --no-emit-package fde-mcp --format requirements-txt --output-file audit-requirements.txt --quiet
uvx --from pip-audit==2.10.1 pip-audit -r audit-requirements.txt --no-deps --disable-pip --progress-spinner off
```

The audit queries a public advisory service with package names and versions, not tokens or ticket data. Only the locally developed source packages are omitted; repository tests/review cover their code. An audit failure blocks the check. A clean result means no known matching advisories at scan time, not absence of vulnerabilities.

Report sensitive issues privately to the owner through an established private channel. Never include real tokens in public issues. Rotate exposed credentials immediately; removal from the latest commit does not erase historical copies.
