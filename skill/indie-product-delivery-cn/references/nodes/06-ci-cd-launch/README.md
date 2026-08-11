# Release 执行

## 阅读相关 workflow

| 需求 | 阅读 |
|---|---|
| 确认 target、source、Node05 证据、环境、pipeline、credentials 以及 readiness | `release-readiness-environment-and-pipeline.md` |
| 执行 rollout、migration、provider action、recovery、smoke/watch 以及 release record | `rollout-recovery-verification-and-record.md` |

所选 workflow 中每条适用的要求都是最低交付标准，因为它们保证 release 可复现、可恢复。仅在确实不相关时才跳过检查。当有助于完成所请求的 release 结果时，可增加准备、验证或执行工作；当必需的 secret 或 API credential 无法获取时，应停止执行。

## Output contract

返回 target 与 source、preflight 事实、执行的 commands/actions、migration 或 deployment 结果、即时的 smoke/watch 证据、recovery 或 rollback 判断、release record，以及任何遗留 gap。区分 planned、ready、executed 与 verified 状态；切勿从准备阶段推断执行已完成。对于每一项变更，包含 commit 与 push 结果，或说明阻止执行的缺失 credential/API-key blocker。
