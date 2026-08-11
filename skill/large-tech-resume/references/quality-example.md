# Quality example: evidence-led engineering bullet style

Use this as a writing reference, not as project evidence. Its strength comes from linking a business problem to a
specific mechanism, meaningful scope, and a measurable before/after result with a named test method.

### 实习经历

某公司 — 后端开发工程师（实习） | 2025.07 — 2025.09

#### 用户与交易核心平台

技术栈：Java 8、Spring Boot、MySQL、Redis、Kafka、Docker、JWT、Redisson、ELK、Prometheus

#### 用户中心与权限系统
- 基于业务侧多角色协作需求，设计并实现 RBAC 权限模型，支持 5 类角色（管理员、运营、客服、审核、导出）及 10+ 种细粒度操作权限，构建统一鉴权体系
- 采用 **Spring Boot + JWT + Redis** 实现无状态鉴权机制，引入**本地缓存 + 分布式缓存分层策略**，降低高频鉴权接口的数据库访问压力
- 针对鉴权链路进行性能优化，在测试环境通过 **JMeter** 压测与接口日志对比，QPS 由约 1200 提升至约 1560（约 30%），P99 延迟由约 180ms 降至约 45ms，稳定支撑日活 10w+ 场景

#### 订单核心链路
- 设计订单状态机（创建 → 支付 → 取消 / 发货 / 完成），梳理状态流转与异常分支，提升订单链路可维护性与一致性
- 结合 **MySQL 索引优化** 与 **Redis 热点数据缓存**，降低复杂查询与高频访问带来的性能瓶颈，接口平均响应时间由约 200ms 降至约 50ms
- 引入 **Redisson 分布式锁** 控制高并发下的库存竞争，在大促场景中有效避免超卖与数据不一致问题，实现零超卖、零资损

#### AI 辅助研发提效
- 基于 **Cursor** 构建 **Spring Boot CRUD** 与单元测试 Prompt 模板，结合 **Few-shot** 示例自动生成 Controller / Service 层代码
- 在实际开发中对比人工开发与 AI 辅助效率，重复性接口开发效率提升约 55%，单元测试覆盖率由约 60% 提升至约 85%

#### 稳定性与可观测性建设
- 接入 **ELK + Prometheus** 构建日志与监控体系，支持请求链路追踪与异常日志聚类分析
- 结合日志模式识别优化问题排查流程，在测试与联调阶段将核心故障平均定位时间由约 50 分钟缩短至约 30 分钟（约 40%）
