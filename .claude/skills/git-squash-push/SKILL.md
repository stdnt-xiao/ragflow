---
name: git-squash-push
description: 将本地分支上所有未推送的 commit 合并（squash）成一个 commit 并推送到远端。适用于以下场景：用户说"合并本地commits推送"、"squash commits and push"、"将未推送的commits合并成一个再推"、"把多个commit压缩成一个"、"整理提交记录再推送"、"本地有多个commit想合并后推送"。即使用户没有明确说 squash，只要意图是"把若干本地提交整合成一个再推"，就应使用本 skill。支持 git worktree 场景，commit message 使用中文。
---

# Git Squash & Push

将本地分支未推送的多个 commit 合并为一个，再推送到远端。

---

## 第一步：侦察阶段（并行执行）

同时运行以下命令，收集全貌：

```bash
git log --oneline -15          # 查看最近提交历史
git status                     # 当前工作区状态
git branch -a                  # 所有分支（+ 表示已在其他 worktree 中检出）
git worktree list              # 列出所有 worktree 及其路径
```

**关键判断：目标分支在哪个 worktree？**

`git branch` 输出中，分支名前的 `+` 表示该分支已被另一个 worktree 检出，不能在当前 worktree 中直接 checkout。

- 若目标分支在**当前** worktree → 直接操作
- 若目标分支在**其他** worktree → 后续所有 git 命令需加 `-C <worktree-path>` 前缀

---

## 第二步：确认 squash 范围

```bash
# 统计本地领先远端的 commit 数
git log origin/<branch>..<branch> --oneline

# 若目标分支在其他 worktree
git -C <worktree-path> log origin/<branch>..<branch> --oneline
```

将结果展示给用户，格式如下：

> 本地 `dev` 分支领先 `origin/dev` **N 个 commit**，将合并为一个：
> - `abc1234` feat: 功能A
> - `def5678` fix: 修复B
> - ...
>
> 请确认是否继续，以及 commit message（或由我自动生成）？

---

## 第三步：生成 commit message

若用户未指定 message，根据这 N 个 commit 的标题**自动生成**一条描述，结构如下：

```
feat: <一句话概括主要功能>

<功能模块A>：
- 具体改动1
- 具体改动2

<功能模块B>：
- 具体改动1
- ...
```

**语言规则**：commit message 必须使用**中文**，无论用户使用何种语言交流。

---

## 第四步：执行 squash

```bash
# 软重置到远端，保留所有改动为已暂存状态
git -C <worktree-path> reset --soft origin/<branch>

# 确认暂存区（可选，供用户核对）
git -C <worktree-path> status --short
```

---

## 第五步：创建合并 commit

```bash
git -C <worktree-path> commit -m "$(cat <<'EOF'
<commit message>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

> **注意**：pre-commit hook 可能会自动格式化部分文件（如 prettier）。这是正常行为，commit 仍会成功。

---

## 第六步：推送

```bash
git -C <worktree-path> push origin <branch>
```

由于这些 commit 原本就没有推送到远端，squash 后推送是**快进（fast-forward）推送**，无需 `--force`。

确认推送成功后，告知用户：
- 合并了多少个 commit
- 新 commit 的 hash
- 推送结果（旧 hash → 新 hash）

---

## 常见问题

**Q：需要 force push 吗？**
不需要。只有当远端已经存在这些 commit（已推送过）时才需要 force push。如果 commit 只在本地，squash 后推送是普通的快进推送。

**Q：worktree 中的分支用 `+` 标记怎么处理？**
用 `git -C <worktree-path>` 代替 `git checkout`，在对应 worktree 路径下直接执行所有操作，避免切换分支。

**Q：reset --soft 会丢失代码吗？**
不会。`--soft` 只移动 HEAD 指针，所有文件改动保留在暂存区，等待重新 commit。
