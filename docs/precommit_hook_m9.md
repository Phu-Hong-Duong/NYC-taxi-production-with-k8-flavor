# The pre-commit hook — M9-S13

*The PO's fourth answer (AWAITING_PO 2026-08-24-5), landed with its limit intact.*

## 0. What was asked, and what was promised alongside it

The M1 prior-art harvest adopted commit-time secret scanning; M9-S9 deliberately
did **not** ship it, on one argument: a hook lives in `.git/hooks`, which git does
not track, so a repository cannot verify its own hook and a claim about it is a
claim nothing here can check. The PO said yes anyway, and accepted that limit in
the same sentence. So this story ships the hook **and** is precise about which
halves are checkable:

| half | checkable? | by what |
|---|---|---|
| the tracked script exists, and git records it **executable** | yes | `git ls-files -s`, in a test |
| the installer copies it and sets the execute bit | yes | a test that RUNS the installer into a temp directory and reads the mode back |
| it refuses a staged credential; it lets ordinary work through | yes | `make hook-redteam`, 20 checks |
| it is installed **in your clone** | **no** | `make install-hooks-check` answers, live; nothing tracked can |
| it cannot be bypassed | **no, and it can** | `git commit --no-verify`, MEASURED in arm C |

**`make security-scan` remains the audit of record.** It reads every tracked file
and every commit on every ref; publishing was made conditional on that, not on
this. The hook is a convenience that shortens the loop from "found at audit time,
now rewrite history and rotate a credential" to "refused before it ever existed".

## 1. One acknowledgement table, and why that decided the shape

The obvious hook is three lines of bash calling `gitleaks` directly. It is the
wrong one here, for a reason that is specific rather than aesthetic.

`scripts/gameday_m6.py` carries a 32-character high-entropy string that is a
credential **by shape** and a non-secret **by fact**: it is the M6-S5 gameday's
deliberately wrong MinIO secret, the value injected to make MinIO refuse the
predictor so A-5 and A-7 can be watched firing. A credential designed not to work
is the one string in this repo that must look exactly like a credential. M9-S9
argued it once, in `ACKNOWLEDGED_SECRETS`, keyed on the sha256 of the found bytes,
and the argument is re-derived from those bytes on every run.

A hook with its own copy of the rules and no copy of that argument refuses every
commit that touches the gameday. The author's second such commit teaches them
`--no-verify`, and the flag they learn on a false positive is the flag they will
reach for on the commit that matters. So the hook runs the **audit's own module**:

```
scripts/hooks/pre-commit  ->  security_scan.py --stage staged-secrets --no-write
```

One table, one redaction, one vocabulary. F-013's "one home for a bar", applied to
a suppression.

## 2. The staged leg

`gitleaks git --staged` — the index, not the disk. The distinction is not
pedantry: a file can be staged clean and dirty in the working tree, or staged
dirty and clean on disk, and it is the **staged** bytes that become a commit.

Three properties are worth reading slowly.

**It never writes.** `main()` refuses `--stage staged-secrets` without
`--no-write`, loudly, rather than forcing the flag. A commit hook that rewrote a
tracked record would dirty the tree inside the commit it is inspecting — F-053 and
F-063's family, third time — and a *silent* force is exactly the defensive default
F-064 was: in a producer it keeps the system running; in a verifier it keeps the
verdict green.

**It is not one of the audit's legs.** `STAGES` is what `make security-scan` runs
and what `scan.json` records; `staged-secrets` lives in `STAGE_CHOICES` only. An
audit record carrying a staged leg would describe whatever happened to be in
somebody's index the minute they ran the audit.

**Its sentences are its own.** The audit prints *secrets in git (tracked files +
full history)*; this leg looked at an index and says *secrets staged for commit*.
Reusing the audit's line would claim a corpus this invocation never opened —
gotcha #78's false green, said by the checker instead of by a panel. The refusal
text differs too: the audit says *park at AWAITING_PO*, the hook says *unstage it,
and do not fix this with `--no-verify`*.

**The command in the charter does not exist.** The charter says
`gitleaks protect --staged`; `protect` was removed in the gitleaks 8.19 line, and
the pinned 8.30.1 binary offers `dir`, `git` and `stdin`. Read off
`gitleaks --help` on the pinned binary rather than off a remembered command —
gotcha #70's family, and it cost one minute instead of one attempt.

## 3. The execute bit is why there is an installer

`cp` would do it. `chmod +x` is why it is a script.

Git records a tracked file's mode, so `scripts/hooks/pre-commit` is `100755` in
the index and a test asserts it. But a hook that arrives at 0644 — from a tarball,
a `curl`, a filesystem that drops the bit, or M8-S4 leg 2's `COPY` — is a hook git
**skips silently**. No error, no scan, and `ls` shows the file sitting right
there. That is the failure mode this program spends most of its guards on: not a
wrong answer, an absent one that reads like a right answer.

So `scripts/install_hooks.sh` sets the bit and then **reads it back off the
installed file** (`deploy_serving.sh`'s idiom — never trust the thing you just
submitted), and `--check` distinguishes the three ways a hook stops being a hook:
absent, stale, and present-but-not-executable. Each is a separate parametrised
test, and the tests install into a temp directory rather than grepping the script
for `chmod`, which would pass on a script that chmods the wrong path.

It never destroys: a pre-existing `pre-commit` that is not ours is left alone and
named, and overwriting it is an explicit `FORCE=1` (`postgres_databases.sh`'s
asymmetry).

## 4. The drill — and the arm that is not about blocking

`make hook-redteam`, **PASSED 20/20**, `automation/runs/m9-hook/redteam.json`.

**Arm A is the load-bearing one.** An ordinary staged file must COMMIT, with the
hook installed, and the hook must be shown to have RUN — a hook that is installed,
executable and doing nothing looks exactly like a hook that passed (gotcha #81 at
the commit boundary). Without arm A, "the plant was blocked" is equally consistent
with a hook that refuses everything, which is worse than no hook at all: it is
uninstalled by Friday.

**Arm B** stages a generated AWS-shaped credential: the commit is refused,
non-zero, naming the file and the reason, printing no secret, **HEAD unmoved**,
and the plant still staged so its author can fix it rather than re-find it.

**Arm C measures the limit rather than restating it.** `git commit --no-verify`
commits the very thing the hook refused, and the hook prints nothing because it
never ran. Then the audit of record is asked, and it catches the bypassed commit —
which is the whole reason the audit and not the hook is what publishing is
conditional on. The plant is then destroyed (branch deleted, reflog expired,
`gc --prune=now`) and `git cat-file -e` is **asked**: "I deleted the branch" and
"the object is gone" are different claims, and only the second is what publishing
cares about.

The drill **installs nothing**. It refuses to run unless the hook is already
installed and current, so it cannot pass against a hook of its own making, and it
cannot leave a clone in a state its owner did not choose.

## 5. F-080 — the hook broke a drill the same hour it was installed

`make security-scan-redteam` had passed 16/16 for a day. With the hook installed
it died at arm B: that arm **stages a credential and commits it on purpose**, and
the hook refused, under `set -e`.

Nothing was wrong. The hook was right, the drill was right, and the interaction
was new. But the shape is worth keeping: **a repo-wide refusal changes the
behaviour of every existing workflow that deliberately does the forbidden thing —
and the workflows that deliberately do forbidden things are the drills.** Exactly
one such caller exists here (`grep -rn "git commit"` over `scripts/`, `automation/`
and the Makefile finds it and nothing else), and it now commits with `--no-verify`
and a comment saying that the flag is there *because the hook is right*.

The general form is F-053 and F-063's, arriving from the other direction: those
were about a command reused as somebody else's undo mutating state that already
existed. This is about a new guard changing the meaning of somebody else's
command. Same question, asked before shipping a refusal: **who already does this
on purpose?**

## 6. The generator stopped being a twin

Both drills need a credential-shaped value drawn against the properties the
DETECTOR keys on. F-071 is the record of what happens otherwise: two runs in five
reported all six detection checks failing — *the scanner found nothing* — because
a base64 `+` truncated `generic-api-key`'s match and a short random string clears
an entropy floor only on average.

A second copy of that generator is a second copy that has not learned F-071. It
now lives once, in `scripts/redteam_plant.py`, with the argument in its docstring
and a property test that draws 25 pairs and asserts the alphabet and both floors.
`test_the_redteam_carries_no_credential_shaped_literal` went red for the move — it
asserted `secrets.choice` appears in the drill — and was **re-derived, not
widened**: the property was always *generated rather than typed*, in this file or
in the shared one (gotcha #50).

## 7. Transcript

```
$ make install-hooks
[hooks] ok  pre-commit -> .git/hooks/pre-commit  (sha256 60d412e51081…, mode 775)
[hooks] Installed into .git/hooks — which git does not track, so nothing in this
[hooks] repository can prove it stayed there. 'make install-hooks-check' asks;
[hooks] 'make security-scan' is the audit of record, hook or no hook.

$ make hook-redteam
[hook-redteam] planted an AWS-shaped pair, id AKIA7MSF… (generated this run)
[hook-redteam]   shannon entropy id/secret: 3.784 4.822 — drawn above the rules' floors

[hook-redteam] arm A — the negative control: an ordinary commit must PASS
  ok  arm A: the commit SUCCEEDS with the hook installed
  ok  arm A: the hook demonstrably RAN (an installed hook doing nothing looks identical)
  ok  arm A: it reported looking at the INDEX, not at the tree or at history
  ok  arm A: HEAD moved (the control really committed)

[hook-redteam] arm B — a staged credential must be REFUSED
[sec-scan] secrets staged for commit: 1
    BLOCKING  generic-api-key  redteam_hook_planted_credential.txt:2  staged for commit — one `git commit` from history
[sec-scan] COMMIT REFUSED: the bytes above are staged, not yet committed.
  ok  arm B: the commit is REFUSED (non-zero from git commit)
  ok  arm B: the refusal names redteam_hook_planted_credential.txt as BLOCKING
  ok  arm B: it gives the reason 'staged for commit'
  ok  arm B: the message says COMMIT REFUSED, not the audit's park-at-AWAITING_PO text
  ok  arm B: it does NOT print the planted secret
  ok  arm B: HEAD did NOT move — nothing was committed
  ok  arm B: the plant is still STAGED, so the author can fix it rather than re-find it

[hook-redteam] arm C — the honest limit, MEASURED: --no-verify bypasses it
  ok  arm C: --no-verify commits the very thing the hook refused (the limit is real)
  ok  arm C: and the hook printed nothing, because it never ran
  ok  arm C: the bypassed commit 430c772 is NOT reachable from story/m9-s13-pre-commit-hook
  ok  the AUDIT still catches it (--all reaches a ref HEAD's ancestry does not)

[hook-redteam] destroying the bypassed commit and re-asking
  ok  the bypassed object is GONE from this clone (not merely unreferenced)
  ok  the untampered audit is GREEN again (exit 0)
  ok  and it reports 0 blocking findings
  ok  HEAD is back where it started (story/m9-s13-pre-commit-hook at 8837b01baab4…)
  ok  the working tree is clean apart from the record this drill is about to write

[hook-redteam] wrote automation/runs/m9-hook/redteam.json
[hook-redteam] PASSED — 20 checks, 0 failures.
```

And the same hook, on this story's own commits — every `git commit` in this
session printed:

```
[sec-scan] staged-secrets
[sec-scan] secrets staged for commit: 0
[sec-scan] OK — nothing staged for this commit is a secret.
```

## 8. What this does not cover

- **Whether it is installed anywhere but here.** Ask `make install-hooks-check`;
  no gate can.
- **`--no-verify`, and any commit made before the hook existed.** The audit's
  history leg walks every ref and is the net under both.
- **Anything but secrets.** It is not a linter, a formatter or a test runner. A
  hook that takes ten seconds is a hook that gets uninstalled; this one takes
  **0.4 s** on a clean index.
- **A secret that does not look like one.** Every scanner-shaped guard here is
  bounded by its rules; the acknowledgement table exists because that boundary
  cuts both ways.
