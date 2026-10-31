# CodeRabbit review

`.coderabbit.yaml` is configuration, not proof that the GitHub App is installed.
Status at setup: **unverified**. Authenticated tooling could list PRs (none existed), but the
repository-installations probe returned HTTP 404 and the user installations API returned 403
(requires a GitHub-App-authorized token). Neither could establish installation status.
No real PR review was observed, and no artificial PR was created to trigger one.

Owner activation, if not already installed: open https://github.com/apps/coderabbitai,
choose **Install**, select the account that owns CivicMesh, choose **Only select repositories**,
select `nishantjadaun26/CivicMesh`, and authorize the requested GitHub App access. If already
installed, use GitHub Settings -> Applications -> Installed GitHub Apps -> CodeRabbit -> Configure
and include this repository. Do not purchase a plan or change billing for this foundation.

On the next genuine implementation PR to main, verify the bot's review, reviewed commit and
configuration. Check the CodeRabbit dashboard/repository settings if no review appears. Only
then record it as verified active and identify the actual check name before requiring it.

The configuration uses English, a quiet review profile, high-level summaries, non-draft
automatic reviews and incremental updates. `base_branches` adds to the default branch, so main
must remain default. Automatic approvals and code-producing finishing touches are disabled;
there is no invented auto-merge setting. Post-merge actions are empty. Team policy prohibits
unsolicited code commits and merging by the bot. Generated types/build files are excluded;
dependency manifests, locks, migrations, source schemas and CI remain in scope.

PR workflow: author opens a small PR; CodeRabbit reviews after activation; author fixes valid
findings and explains incorrect ones with evidence; teammate reviews; CI passes; human merges.
Manual commands, verified against the official review command reference:

```text
@coderabbitai review
@coderabbitai full review
```

The first requests an incremental review; the second requests a full review. Use genuine PRs.
CodeRabbit does not replace tests, privacy review, or human understanding.

Validate changes with `scripts/validate_coderabbit.py` after downloading the official schema.
CI repeats validation. If official fields change, inspect the new schema instead of guessing keys.

Local PowerShell validation (Python 3.11+):

```powershell
python -m pip install jsonschema==4.26.0 PyYAML==6.0.3
New-Item -ItemType Directory -Force .cache | Out-Null
Invoke-WebRequest https://coderabbit.ai/integrations/schema.v2.json -OutFile .cache/coderabbit-schema.json
python scripts/validate_coderabbit.py
```

This is configuration validation only. No frontend/backend implementation or application
test workflow is included in the trimmed setup.

Sources: [configuration](https://docs.coderabbit.ai/reference/configuration),
[schema](https://coderabbit.ai/integrations/schema.v2.json),
[commands](https://docs.coderabbit.ai/reference/review-commands).
