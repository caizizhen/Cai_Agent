# GitHub 推送失败：HTTPS 不通时用 SSH 走 443

## 现象

- `git push` 使用 `https://github.com/...` 时出现 **`Failed to connect to github.com port 443`** 或长时间超时。
- 同一网络下 **`Test-NetConnection ssh.github.com -Port 443`** 为 **`TcpTestSucceeded : True`**，说明可走 GitHub 提供的 **SSH over HTTPS 端口**。

## 处理步骤（Windows / OpenSSH）

1. **在用户目录** 确保存在 **`%USERPROFILE%\.ssh`**。
2. 若还没有密钥：`ssh-keygen -t ed25519 -C "your-id" -f "%USERPROFILE%\.ssh\id_ed25519"`（按提示设置口令或回车）。
3. 新建或编辑 **`%USERPROFILE%\.ssh\config`**，加入（与 [GitHub 文档](https://docs.github.com/zh/authentication/connecting-to-github-with-ssh/using-ssh-over-the-https-port) 一致）：

```sshconfig
Host github.com
  HostName ssh.github.com
  Port 443
  User git
```

4. 将 **`id_ed25519.pub`** 全文复制到 GitHub：**Settings → SSH and GPG keys → New SSH key**。
5. 本仓库改用 SSH 远程（仅需在本机执行一次）：

```powershell
git remote set-url origin git@github.com:caizizhen/Cai_Agent.git
```

6. 验证：`ssh -T git@github.com` 应出现 *Hi \<user\>! You've successfully authenticated...*，再执行 **`git push origin main`**。

## 说明

- **`ssh-keyscan`** 在部分 Windows OpenSSH 版本上可能对 `ssh.github.com` 报 KEX 错误；首次用 **`ssh -T`** 时可用 **`StrictHostKeyChecking=accept-new`** 写入 **`known_hosts`**。
- 若团队仍希望默认使用 HTTPS，可在网络恢复后改回：`git remote set-url origin https://github.com/caizizhen/Cai_Agent.git`。
