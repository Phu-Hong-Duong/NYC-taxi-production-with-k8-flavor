# AWAITING_PO — the one inbox (newest on top; the chain parks affected paths here)

Format per entry: date · raised by (session/role) · the fork in plain language ·
2–3 options with honest trade-offs (the recommendation must state the cost of
the honest option — never the demo-easy path dressed as best) · what is parked ·
what continues meanwhile. You answer by editing the entry with your choice,
then resume the chain (`automation/next_session.sh executor` — or `architect`
if the answer changes the plan). Direction decisions WAIT here; nothing
auto-proceeds on a recommendation (ADR-010).

## 2026-08-16-1 · raised by ARCH/Fable (Session 1, bootstrap) · GO-LIVE: the chain's home isn't ready, and only your hands can finish it

**The fork in plain language.** The program is designed to run inside WSL2
(CLAUDE.md, gotcha #1, automation/README one-time setup). Preflight found the
Windows side healthy (git+push ✅, gh ✅, claude 2.1.233 ✅, Docker 29.6.2 ✅,
all ports free ✅, TLS clean ✅) but the WSL side not ready: no repo clone
there, `claude` and `gh` not installed in Ubuntu, permission flags unset,
RAM grant 31 GB (< 48), Docker's WSL integration OFF. Four of those need
interactive logins, a GUI toggle, sudo, or a risk decision — all yours by
constitution (credentials and permission modes never ride a default,
gotcha #23). Everything scriptable is already done: harness PROVEN on the
real CLI (hello-chain + STOP kill switch, quoted in HANDOFF k), M0 kickoff
authored, chain-script exec bit fixed, `.wslconfig` (48GB) written, WSL clone
pre-staged at `~/NYC-taxi-production-with-k8-flavor`, all pushed.

**Option A (Recommended) — finish the WSL setup: ~15 minutes of your hands,
the paste-block below.** Honest cost: your time, two browser logins, one
permission-mode risk call; the chain starts the moment the last line runs.
This is the designed path — every gotcha and rehearsed recovery in the ledger
assumes it.

**Option B — re-platform to run Windows-native (Git Bash).** Zero setup now
(claude/gh already live on Windows — the hello-proof even ran there), but:
an unplanned porting effort (Makefile, scripts, kind/kubectl flows and ALL
rehearsed gotchas are Linux-assumed), the CRLF trap class reopens (#11), and
you STILL owe the permission-mode decision — the one human step no platform
removes. This is the demo-easy path; its cost hides downstream. Not
recommended.

**What is parked:** the entire chain — every M0 story needs the WSL home; no
independent story exists. **What continues meanwhile:** nothing autonomous;
the repo is build-ready and pushed (`origin/main`).

**Answer by DOING Option A's block (running its last line IS the answer — the
chain self-starts), or by editing this entry with "B" (ARCH will then re-plan
M0 for Windows-native).**

---

### Option A paste-block (once, in order)

**A1. (Windows)** Docker Desktop → Settings → Resources → **WSL integration**
→ toggle **Ubuntu** ON → Apply & restart.

**A2. (Windows PowerShell)** `wsl --shutdown` — applies the 48 GB grant
already written to `C:\Users\longt\.wslconfig`. If Docker Desktop complains
afterwards, quit and reopen it.

**A3. (new Ubuntu terminal)**
```bash
free -h            # expect ~47Gi total (was 31Gi)
docker ps          # expect an empty table, no error
sudo apt update && sudo apt install -y make gh
cd ~/NYC-taxi-production-with-k8-flavor
git config --global user.name  "Phu-Hong-Duong"
git config --global user.email "dhphu222@gmail.com"
gh auth login      # browser flow; pick HTTPS
gh auth setup-git  # lets the chain push over HTTPS
curl -fsSL https://claude.ai/install.sh | bash    # probed 200 on 2026-08-16
exec $SHELL -l
claude --version   # expect 2.x
claude             # complete /login in the browser, then /exit
```

**A4. Permission mode — YOUR risk call (automation/README.md §setup). Pick ONE:**

Safer (unattended sessions may park on unlisted commands — extend the list):
```bash
cd ~/NYC-taxi-production-with-k8-flavor
mkdir -p .claude && cat > .claude/settings.local.json <<'EOF'
{
  "model": "opus",
  "permissions": {
    "allow": [
      "Bash(make:*)", "Bash(kubectl:*)", "Bash(helm:*)", "Bash(kind:*)",
      "Bash(docker:*)", "Bash(git:*)", "Bash(gh:*)", "Bash(uv:*)",
      "Bash(dbt:*)", "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
      "Bash(dvc:*)", "Bash(curl:*)", "Bash(ss:*)", "Bash(free:*)",
      "Bash(automation/next_session.sh:*)"
    ]
  }
}
EOF
echo 'export CLAUDE_PERMISSION_FLAGS="--permission-mode acceptEdits"' >> ~/.bashrc
```
Simpler, riskier (it can run anything unattended — your machine, your call):
```bash
echo 'export CLAUDE_PERMISSION_FLAGS="--dangerously-skip-permissions"' >> ~/.bashrc
```

**A5. Start the chain — and keep this Ubuntu window OPEN (gotcha #24: the
scheduler lives in WSL):**
```bash
exec $SHELL -l
cd ~/NYC-taxi-production-with-k8-flavor
automation/next_session.sh executor 60
```

*Postscripts:* your PyCharm copy on `C:\` stays your viewing window — `git
pull` there to see the chain's work; the chain itself only ever runs in the
WSL clone. The untracked `_to_delete/git-locks/` files in the Windows copy
are yours to delete at leisure; the chain will not touch them.
