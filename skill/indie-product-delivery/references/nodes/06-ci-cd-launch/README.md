# 发布执行

## 阅读相关工作流

| 需求 | 阅读 |
|---|---|
| 确立目标、源、Node05 证据、环境、pipeline、凭证和就绪状态 | `release-readiness-environment-and-pipeline.md` |
| 执行 rollout、migration、provider 操作、恢复、smoke/watch 和发布记录 | `rollout-recovery-verification-and-record.md` |

所选工作流中每个适用的要求都是最低交付标准,因为它使发布可复现且可恢复。仅跳过确实无关的检查。当有助于完成所请求的发布结果时,可添加准备、验证或执行工作;当所需的 secret 或 API 凭证不可用时停止。

## 输出契约

返回目标和源、预检事实、执行的命令/操作、migration 或 deployment 结果、即时 smoke/watch 证据、恢复或 rollback 判断、发布记录,以及任何剩余的差距。区分 planned、ready、executed 和 verified 状态;切勿从准备推断执行。对于每个变更,包含 commit 和 push 结果,或阻止其执行的缺失凭证/API key 阻塞项。