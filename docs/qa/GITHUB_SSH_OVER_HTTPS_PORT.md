# GitHub push fails on HTTPS: use SSH on port 443

## Symptoms

- `git push` to `https://github.com/...` fails with **`Failed to connect to github.com port 443`** or long timeouts.
- On the same network, **`Test-NetConnection ssh.github.com -Port 443`** returns **`TcpTestSucceeded : True`**, so GitHub’s **SSH over the HTTPS port** path works.

## Fix (Windows / OpenSSH)

1. Ensure **`%USERPROFILE%\.ssh`** exists.
2. If you have no key yet: `ssh-keygen -t ed25519 -C "your-id" -f "%USERPROFILE%\.ssh\id_ed25519"`.
3. Create or edit **`%USERPROFILE%\.ssh\config`** with ([GitHub docs](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/using-ssh-over-the-https-port)):

```sshconfig
Host github.com
  HostName ssh.github.com
  Port 443
  User git
```

4. Add **`id_ed25519.pub`** to GitHub: **Settings → SSH and GPG keys → New SSH key**.
5. Point this repo at SSH (once per clone):

```powershell
git remote set-url origin git@github.com:caizizhen/Cai_Agent.git
```

6. Verify: `ssh -T git@github.com` should greet your user; then **`git push origin main`**.

## Notes

- Some Windows **`ssh-keyscan`** builds fail KEX negotiation with `ssh.github.com`; first **`ssh -T`** with **`StrictHostKeyChecking=accept-new`** can populate **`known_hosts`** instead.
- To switch back to HTTPS after the network issue is gone: `git remote set-url origin https://github.com/caizizhen/Cai_Agent.git`.
