# 安全与可靠性

针对独立产品风险校准的安全审查。一个独立产品通常具有数据库、用户认证、API 端点、可选的文件上传、第三方集成(支付、邮件)和环境变量。本文档覆盖真实的安全面,而非企业级审计。

STANDARD 变更运行 CP9 基线项加 CP11 基本扫描。HIGH_RISK 变更运行 CP9 全部、CP10 和 CP11 完整扫描。

## CP9: 完整安全审查

### 9A 数据库安全

| 检查项 | 要发现什么 | 严重级别 |
| --- | --- | --- |
| SQL 注入 | 使用字符串拼接 SQL 而非参数化查询;ORM 原始查询包含用户输入 | Blocker |
| 连接字符串 | 数据库密码硬编码在源码中;连接字符串出现在日志或错误消息中 | Blocker |
| 数据库权限 | 应用以 root 或 superuser 连接而非最小权限用户 | Major |
| 数据库文件暴露 | SQLite 文件在可 Web 访问的目录中;数据库备份在公开路径上 | Blocker |
| Migration 安全 | migration 脚本不可逆且无备份计划;migration 锁表导致停机 | Major |
| 查询安全 | 无界查询(列表或导出无 LIMIT);N+1 查询泄露数据 | Major |
| 事务安全 | 多写操作无事务包装;部分失败导致不一致状态 | Major |

### 9B 数据隐私安全

| 检查项 | 要发现什么 | 严重级别 |
| --- | --- | --- |
| PII 日志 | 敏感数据(邮箱、电话、地址、身份证号)出现在日志、控制台、错误消息或 URL 参数中 | Blocker |
| API 响应中的 PII | API 返回不必要的敏感字段(例如用户列表响应包含密码哈希) | Blocker |
| HTTPS | 未强制 HTTPS;API 端点允许 HTTP;混合内容(HTTPS 页面上的 HTTP 资源) | Blocker |
| 传输中数据 | 密码或 token 通过明文 HTTP 发送;API 调用无 TLS | Blocker |
| 密码存储 | 密码明文存储或使用弱哈希(MD5、SHA1);应使用 bcrypt 或 argon2 | Blocker |
| Cookie 安全 | session cookie 缺少 HttpOnly、Secure 或 SameSite 属性 | Blocker |
| localStorage 滥用 | token 或敏感数据存储在 localStorage(可被 XSS 读取)而非 httpOnly cookie | Major |
| 数据最小化 | 收集功能不需要的用户数据;收集了但从未使用的字段 | Major |
| 数据留存 | 无留存或删除策略;无用户删除请求的处理逻辑 | Major |

### 9C API 安全

| 检查项 | 要发现什么 | 严重级别 |
| --- | --- | --- |
| 端点认证 | API 端点缺少认证守卫(明确公开的除外) | Blocker |
| IDOR | 按 ID 访问资源而无所有者或租户检查(例如 `/api/users/123` 未验证 123 属于当前用户) | Blocker |
| 输入验证 | API body、query 或 params 无类型、schema 或大小验证 | Major |
| 速率限制 | 高风险端点(认证、密码重置、注册)无速率限制 | Major |
| CORS | `Access-Control-Allow-Origin: *` 与 `credentials: true` 组合;或允许任意来源 | Blocker |
| 错误披露 | API 错误响应包含堆栈跟踪、SQL、内部路径或数据库结构 | Major |
| 文件上传验证 | 无文件类型或大小检查;上传路径可被遍历;文件名未清洗或重命名 | Blocker |
| 文件上传存储 | 上传文件存储在可 Web 访问的路径且可执行(例如 `.php`、`.js`) | Blocker |
| 批量操作安全 | 批量删除或更新无确认或二次权限检查 | Major |

### 9D 认证与授权

| 检查项 | 要发现什么 | 严重级别 |
| --- | --- | --- |
| 密码安全 | 明文存储;弱哈希;无最低复杂度要求 | Blocker |
| Token 安全 | JWT 无过期时间;JWT 密钥硬编码;refresh token 未轮换 | Blocker |
| Session 安全 | 登出时 session 未失效;session 固定(登录后 session ID 未轮换) | Blocker |
| 权限提升 | 普通用户可访问 admin 路由;角色字段可被客户端篡改 | Blocker |
| 暴力破解 | 登录端点无失败次数限制、锁定或验证码 | Major |
| 密码重置 | 重置 token 无过期时间;重置 token 可预测;重置后旧 session 未失效 | Blocker |
| OAuth | OAuth state 参数缺失或未检查(CSRF);redirect URI 未验证 | Blocker |

### 9E 依赖与环境

| 检查项 | 要发现什么 | 严重级别 |
| --- | --- | --- |
| 仓库中的密钥 | `.env` 或配置文件包含密钥但未在 `.gitignore` 中;密钥已提交到 git 历史 | Blocker |
| 依赖漏洞 | `npm audit`、`pip audit`、`cargo audit` 或 `yarn audit` 报告高风险漏洞 | Blocker(高)/ Major(中) |
| 虚构依赖 | 已安装的包不存在(LLM 虚构);已安装的包已弃用或已知恶意 | Blocker |
| Lockfile | lockfile 不一致或缺失(导致依赖漂移) | Major |
| 环境配置 | 生产环境使用开发配置(debug=True,详细错误输出);必需环境变量缺失且无降级处理 | Major |
| 容器 | 容器以 root 运行;镜像包含密钥;暴露不必要的端口 | Major |

### 9F 前端安全

| 检查项 | 要发现什么 | 严重级别 |
| --- | --- | --- |
| XSS | `innerHTML`、`dangerouslySetInnerHTML` 或 `v-html` 渲染用户输入;输出未编码 | Blocker |
| CSP | 无 Content-Security-Policy 头,或头允许 `unsafe-inline` 或 `unsafe-eval` | Major |
| CSRF | 状态变更请求无 CSRF token;或使用 GET 触发写操作 | Blocker |
| 开放重定向 | 重定向 URL 来自用户输入且未对照白名单验证 | Major |
| 客户端密钥 | API key 或密钥硬编码在前端代码中(用户可见) | Blocker |
| postMessage | `window.postMessage` 接收方未验证 origin | Major |

### STANDARD 基线

对于 STANDARD 变更,至少运行:仓库密钥检查(9E)、XSS 检查(9F)、依赖漏洞扫描(9E)和 HTTPS 检查(9B)。这四项是独立产品基线,与风险级别无关。

## CP10: 可靠性

仅检查由变更触发的项目。将确实无关的项目标记为 NOT_APPLICABLE 并附一行原因。

| 检查项 | 何时检查 | 要发现什么 |
| --- | --- | --- |
| 错误处理 | 所有变更 | 错误被捕获、映射为用户可见消息,而非被静默吞没 |
| 重试与超时 | 网络或外部服务调用 | 有界超时,无无限重试,存在退避策略 |
| 幂等性 | 写入、支付、回调 | 重复请求不会创建重复数据或双重扣费 |
| 并发 | 共享状态或异步操作 | 无竞态条件,无死锁,锁正确释放 |
| 数据一致性 | 多写或事务操作 | 事务原子性,部分失败不破坏不变量,rollback 正确 |
| 资源泄漏 | 文件、连接或进程处理 | 异常路径上资源已关闭;无连接池耗尽风险 |

## CP11: 安全验证

### 非破坏性负向检查

使用本地或 staging 测试账户。不要访问其他用户的真实数据、暴力破解凭证、运行 DoS、进行真实支付或运行第三方扫描器。

| 验证项 | 如何执行 | 预期结果 |
| --- | --- | --- |
| 未认证访问 | 在无 token 的情况下调用需要认证的端点 | 401 或 403,不返回数据 |
| 未授权访问 | 使用用户 A 的 token 访问用户 B 的资源 | 403,不返回数据 |
| 无效输入 | 发送格式错误、过大或意外类型的数据 | 400 并附有意义的错误,无崩溃 |
| SQL 注入 | 在输入字段中发送 `' OR 1=1 --` | 不返回额外数据,不暴露 SQL 错误 |
| XSS | 在输入字段中发送 `<script>alert(1)</script>` | 存储并查看时不执行 |
| 过期 token | 使用过期 token 访问端点 | 401,不返回数据 |
| 文件上传 | 上传可执行文件、过大文件或无类型文件 | 被拒绝 |
| 密码重置 | 使用过期或已使用的重置 token | 被拒绝 |

### 工具扫描

运行仓库已有的安全工具。除非用户同意,否则不要安装新工具。

- 依赖审计:`npm audit`、`pip audit`、`cargo audit`、`yarn audit`(适用哪个用哪个)。
- Lint 和静态分析:许多 linter 能检测 XSS 和注入模式。运行仓库已配置的任何工具。
- SAST:如果仓库已配置 CodeQL、Semgrep 或类似工具,则运行它。

当工具不可用时,标记 NOT_RUN 并说明缺少什么。不要报告未实际执行的扫描结果。

### 需记录的发现

对于每个确认的安全发现,说明利用路径:攻击者可控的输入、其遵循的数据或控制路径、缺失或被绕过的控制,以及由此产生的影响。引用确切的文件、行号或配置。指明修复责任人和修复后需要重新测试的内容。