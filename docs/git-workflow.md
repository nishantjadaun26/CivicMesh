# Three-person integration workflow

All three feature branches share the folder-only setup and CodeRabbit configuration. `main` is integrated.
Each teammate uses their own clone:

```powershell
# Teammate 1
git clone --branch feat/frontend https://github.com/nishantjadaun26/CivicMesh.git CivicMesh-frontend
# Teammate 2
git clone --branch feat/ai-workflow https://github.com/nishantjadaun26/CivicMesh.git CivicMesh-ai
# Teammate 3
git clone --branch feat/backend https://github.com/nishantjadaun26/CivicMesh.git CivicMesh-backend
```

For an existing clean clone, `git fetch origin` then `git switch --track origin/feat/frontend`
(substitute the relevant branch); if the local branch already exists, use `git switch feat/frontend`.
Save uncommitted changes intentionally before switching; never reset them to match a remote.

Open small, frequent non-draft PRs from the module branch into main. State the actual behavior,
schema effects and verification. CodeRabbit reviews when its GitHub integration is active.
Evaluate each finding, fix valid issues, explain incorrect suggestions with evidence. A teammate
reviews the changes; required CI must pass before merging. CodeRabbit does not replace tests
or human understanding. See [review setup and commands](code-review.md).

Bring integrated work back into each module branch frequently:

```powershell
git switch feat/ai-workflow
git fetch origin
git merge origin/main
# Resolve conflicts deliberately, then rerun checks.
git push origin feat/ai-workflow
```

Use merge commits for long-lived shared branches to preserve ancestry. Do not force-push, delete
teammates' branches, or overwrite history. A squash merge can be used for short-lived topic PRs,
but these long-lived module branches are easiest to maintain with normal merge commits.
Coordinate shared files before editing. When contracts and dependencies are introduced,
regenerate contracts and commit dependency locks with their corresponding changes.

Recommended main protection: PR required, at least one human approval, required observed CI
checks, conversations resolved, no force pushes. Only CodeRabbit configuration validation is
currently configured; application checks should be added with implementation. Repository settings were not
changed. Do not require an assumed CodeRabbit status name; verify the actual successful check on
a genuine PR first. Ensure main remains the default branch for CodeRabbit's main-only automation.

If main is protected during setup, push a setup/foundation branch and open a genuine foundation
PR, then merge through normal policy. The feature branches can share that foundation commit;
bring origin/main into them after integration. Never bypass protection.
