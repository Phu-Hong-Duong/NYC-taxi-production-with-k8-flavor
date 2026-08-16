# WSL bootstrap — the gotcha #1 fix (run once, inside WSL/Ubuntu)

The execution copy must live in the WSL2 filesystem (/home/...), never /mnt/c.
Paste this block into a WSL terminal:

    git clone /mnt/c/Users/longt/PycharmProjects/NYC-taxi-production-with-k8-flavor \
        ~/NYC-taxi-production-with-k8-flavor
    cd ~/NYC-taxi-production-with-k8-flavor
    git remote set-url origin https://github.com/Phu-Hong-Duong/NYC-taxi-production-with-k8-flavor.git
    chmod +x automation/next_session.sh
    pwd   # must start with /home — gotcha #1 satisfied

Then: automation/README.md one-time setup -> `claude --model fable` here ->
paste Prompt A (docs/PROMPTS.md). The WSL clone is THE working copy (chain,
cluster, git autonomy). This Windows folder stays as your PyCharm mirror —
or open the WSL copy directly in PyCharm via \\wsl$ and keep one copy.
If the first `git push` asks for auth: `gh auth login` (Session 1's
preflight verifies push rights anyway).
