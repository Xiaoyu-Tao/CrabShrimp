# 虾兵蟹将（CrabShrimp）架构机制说明

> 当前版本：**v0.3（含 HITL）**
> 本文描述的是"代码里已经存在的机制"，并明确区分已落地能力与预留扩展点。

---

## 1. 项目定位

虾兵蟹将不是一个"单 Agent 直接回答问题"的应用，而是一个轻量多智能体运行时，包含两条平行能力线：

1. **多智能体协同决策**：任务分角色执行，关键节点触发 Coral-Meeting 集体审议。
2. **自主演化**：跨任务分析 Trace 信号，自动更新 Agent 贡献分、积累可复用 Skill、调整会议拓扑。
3. **人在回路（HITL）**：在关键检查点暂停执行，等待人工审核与干预，支持批准、修改或终止。

版本演化路径：

| 版本 | 核心能力 |
|------|----------|
| v0.1 | 多角色协同、Coral-Meeting、ResourceGuard、JSONL Trace |
| v0.2a | SQLite 数据持久化（agent_profiles / task_records / meeting_outcomes） |
| v0.2b | 真实结果信号（Critic ACCEPTABLE/REJECTED，Verifier VERIFIED/NOT VERIFIED）+ Shell-Molting 演化引擎 |
| v0.3 | Skill 知识库（提取 + 注入）+ 拓扑调整（role_weights + bench_threshold）+ SyncP2P 接入 CoralMeeting |
| v0.3（HITL）| Human-in-the-Loop 守门机制：三个检查点 + HumanGate 组件 |

主执行入口：

- `crabshrimp.cli.commands:run`
- `crabshrimp.runtime.runner.TaskRunner`
- `crabshrimp.dragon_king.orchestrator.DragonKing`

---

## 2. 角色与拓扑结构

### 2.1 顶层拓扑

```text
用户任务
  |
  v
CLI / TaskRunner
  |
  v
DragonKing（总调度器）
  |
  +--> TaskClassifier（任务分类）
  |
  +--> ExecutionPlanner（生成执行计划）
  |
  +--> Role Agents（按步骤执行）
  |       |
  |       +--> Planner
  |       +--> Executor     ← Skill 注入 + 工作空间隔离 + 子进程隔离
  |       +--> Critic        ← 上下文隔离 + 真实 QUALITY 判定
  |       +--> Verifier      ← 上下文隔离 + 真实 VERIFIED 判定
  |       +--> Summarizer
  |
  +--> CoralMeeting（关键节点协商，含 SyncP2P 批评传递）
  |
  +--> AsyncBlackboard（共享状态）
  |
  +--> ResourceGuard（步数 / token 预算控制）
  |
  +--> HumanGate（HITL 检查点：计划审核 / 共识审核 / Verifier 失败介入）
  |
  +--> TraceCollector / TraceWriter（过程记录）
  |
  v
最终输出 + JSONL trace
  |
  v（任务结束后）
ShellMolting（分析 Trace → 更新 contribution_score + role_weights）
  |
SkillExtractor（提取成功步骤的推理 Skill → 写入 SQLite）
```

### 2.2 核心角色

当前角色定义在 `xiabing/models/agent_profile.py`，固定有 5 类：

| 角色 | 职责 | 默认隔离配置 |
|------|------|--------------|
| Planner | 结构化分析，给出计划 | shared 上下文 / 无工作空间 / local |
| Executor | 执行子任务，主力产出 | shared 上下文 / scoped 工作空间 / subprocess |
| Critic | 发现风险与缺陷，QUALITY: ACCEPTABLE/REJECTED | isolated 上下文 / 无工作空间 / local |
| Verifier | 独立校验结果，VERIFIED/NOT VERIFIED | isolated 上下文 / 无工作空间 / local |
| Summarizer | 整合多步产出，形成最终答案 | shared 上下文 / 无工作空间 / local |

### 2.3 角色注册与工厂

系统采用"注册表 + 工厂 + SQLite"三层结构：

1. **AgentRegistry**：SQLite 支撑，`seed_defaults()` 在首次运行时写入默认配置，后续跑保留历史 `contribution_score`。
2. **AgentFactory**：根据 profile 创建 Agent 实例，v0.3 起可向 factory 注入 `SkillRepository`，在 `create(profile, task_category)` 时自动拼接 Top-3 Skill 到 system_prompt。
3. **BaseAgent**：规定每个 Agent 实现 `think()` 和 `act()`。

### 2.4 拓扑调整（v0.3）

`DragonKing._get_meeting_participants()` 在组建 Coral-Meeting 参与者时，会查询 `RoleWeightRepository` 中各 Agent 在当前 `task_category` 下的历史胜率：

- 胜率 ≥ `bench_threshold`（默认 0.5）：正常参与会议。
- 胜率 < `bench_threshold`：被 bench，不进入本次会议。

新 Agent 无历史记录时默认胜率为 1.0，保证首次参与机会。

---

## 3. 智能体通信机制

### 3.1 两类通信

项目有两种通信抽象，两者在 v0.3 均已接入主流程：

| 通信方式 | 模块 | 状态 |
|----------|------|------|
| 共享黑板 | `AsyncBlackboard` | 全流程使用（步骤产物共享） |
| 点对点 | `SyncP2P` | v0.3 接入 CoralMeeting 交叉反思阶段 |

### 3.2 黑板通信

`AsyncBlackboard` 提供两类能力：

1. `set_state(key, value)` / `get_state(key)`：共享 KV 状态。
2. `publish(topic, message)` / `subscribe(topic)`：按主题发布与消费。

主流程中每步结束后写入 `step_<step_id>_output`，Coral-Meeting 共识结果同样写入黑板。

### 3.3 点对点通信（v0.3 接入）

`SyncP2P` 基于内存队列，提供 `send(to_agent_id, message)` / `receive(agent_id, timeout)`。

v0.3 起在 `CoralMeeting` 的 Step 2（交叉反思）阶段正式启用：

1. 每个 Agent 写完对其他立场的批评后，将批评内容通过 `SyncP2P.send()` 投递到被批评方的收件箱。
2. 所有批评写完后，每个 Agent 从收件箱中 `receive()` 发给自己的批评消息。
3. P2P 消息以 `reaction="disagree"` 追加到 Trace 的 `Interaction` 记录中，使 Trace 能反映真实的点对点批评流向。

---

## 4. 状态同步管理机制

### 4.1 状态分层

| 状态类型 | 存储位置 |
|----------|----------|
| 任务级（task_id、分类、计划） | DragonKing 内存 |
| 步骤级（last_output、all_outputs） | DragonKing 内存 + AsyncBlackboard |
| Agent 元状态（contribution_score、隔离模式） | SQLite agent_profiles |
| 运行记录（TraceStep、Interaction） | JSONL 文件 |
| 任务摘要（步数、category、stopped_early） | SQLite task_records |
| 会议结果（winner_agent_id） | SQLite meeting_outcomes |
| Skill 知识库（role、task_category、content） | SQLite skills |
| 角色胜率（task_category、role、agent_id、wins/total） | SQLite role_weights |

### 4.2 SQLite Schema（v0.3）

```sql
agent_profiles   -- agent 配置 + contribution_score（跨任务持久化）
task_records     -- 任务摘要
meeting_outcomes -- Coral-Meeting 胜负结果
skills           -- Skill 知识条目（role × task_category）
role_weights     -- Agent 胜率（task_category × role × agent_id）
```

### 4.3 同步时机

每步执行后：更新 `last_output` → 追加 `all_outputs` → 写 trace → 同步到黑板。

任务结束后（按顺序）：

1. `ShellMolting.evolve()` 分析 Trace 信号，更新 `contribution_score` 和 `role_weights`。
2. `SkillExtractor.extract_and_save()` 对成功步骤调 LLM 提炼 Skill，写入 `skills` 表。
3. `TaskRepository.save()` 写入本次任务摘要。

---

## 5. 环境隔离与资源控制

### 5.1 三层隔离

v0.2 引入三种隔离维度，每种均有独立的 config 开关：

| 隔离类型 | 开关 | 作用 |
|----------|------|------|
| 上下文隔离 | `context_isolation_enabled` | `isolated` 模式的 Agent 只看到紧邻上一步输出，防止锚定偏差 |
| 工作空间隔离 | `workspace_isolation_enabled` | `scoped` 模式的 Agent 拥有独立临时目录 `/tmp/xiabing/<task_id>/<agent_id>/` |
| 执行环境隔离 | `exec_isolation_enabled` | `subprocess` 模式的 Agent 在隔离子进程中运行命令（`asyncio.create_subprocess_shell`，带 timeout） |

默认：Executor 使用 `scoped + subprocess`；Critic / Verifier 使用 `isolated`。

### 5.2 Sandbox 实现

| 实现 | 状态 |
|------|------|
| `LocalSandbox` | 已实现，不隔离，用于本地命令执行 |
| `SubprocessSandbox` | 已实现，基于 asyncio 子进程，支持超时 |
| `DockerSandbox` | Stub，`NotImplementedError`，预留接口 |

### 5.3 资源控制

`ResourceGuard` 管理两类预算：

1. **步数限制** `step_limit`：每步执行前调用 `check_and_consume_step()`。
2. **Token 预算** `token_budget`：每步输出和会议共识后调用 `check_and_consume_tokens()`。

超限时触发"优雅停止"：Summarizer 汇总已有部分结果后返回，`stopped_early=True` 写入任务记录。

---

## 6. 冲突消解与共识机制

### 6.1 CoralMeeting 五步流程

关键节点会触发 `CoralMeeting.convene()`，执行以下 5 步：

1. **陈述**：各参与 Agent 对 topic 独立表达立场。
2. **交叉反思**（v0.3 含 SyncP2P）：每个 Agent 批评其他立场，批评内容通过 P2P 投递到被批评方收件箱，并记录在 Trace。
3. **加权投票**：按 `contribution_score` 赋予每个立场权重。
4. **裁决**：权重最高者立场被采纳；若平票（差值 < 0.01），调用 LLM 仲裁，`winner_agent_id = None`。
5. **记录**：共识结果写入 JSONL trace 和 SQLite `meeting_outcomes`。

### 6.2 参与者确定（含拓扑筛选）

`_get_meeting_participants()` 候选角色为：当前步骤主角色 + Critic + Verifier。

v0.3 起，每个候选 Agent 需通过 `role_weights` 胜率检查（低于 `bench_threshold` 的被 bench 出局）。

---

## 7. Human-in-the-Loop（HITL）

### 7.1 设计原则

HITL 机制将人工判断注入自动化流程的关键节点，不破坏无人值守运行（`hitl_enabled` 默认关闭）。

三种操作均通过 CLI 交互实现：
- **[A] 批准**：接受当前内容，继续执行
- **[E] 修改**：提供修订内容替换当前输出，继续执行
- **[X] 终止**：抛出 `HumanAborted` 异常，`runner.py` 捕获并返回终止结果

### 7.2 三个检查点

| 检查点 | 位置 | 配置开关 | 支持操作 |
|--------|------|----------|----------|
| **执行计划审核** | `ExecutionPlanner.plan()` 完成后、执行开始前 | `hitl_on_plan` | A / X |
| **Coral-Meeting 共识审核** | `CoralMeeting.convene()` 返回 consensus 后 | `hitl_on_critical` | A / E / X |
| **Verifier 失败介入** | Verifier 步骤 `result="failure"` 后 | `hitl_on_verify_fail` | A / E / X |

**检查点 1（执行计划）**：展示完整步骤列表（含角色分配、关键节点标注），人工确认计划合理后再开始执行。

**检查点 2（Coral-Meeting 共识）**：展示会议达成的共识文本。人工修改后的内容将作为新的 `last_output` 进入后续步骤，Shell-Molting 和 Skill 提取均使用修订后的版本。

**检查点 3（Verifier 失败）**：展示 Verifier 的验证推理（截取前 800 字符）。人工可强制放行（approve）、提供修订输出（edit）或终止任务（abort）。注意：Trace 中仍记录 `result="failure"`，Shell-Molting 的归因惩罚依然生效。

### 7.3 核心组件

`xiabing/tidal_pool/human_gate.py`：

- `HumanGate(enabled, input_fn)`：主组件，`input_fn` 可注入 mock 输入用于测试
- `HumanGateResult(decision, edited_content)`：检查点返回值
- `HumanAborted`：用户终止时抛出的异常，`runner.py` 统一捕获处理

### 7.4 与其他模块的关系

- HITL 检查点 2 的修订内容会覆盖 Coral-Meeting 的 consensus，但 `meeting_outcomes` 中记录的仍是原始会议胜者，不受影响
- 检查点 3 的 approve 不改变 Trace 中的 `result="failure"`，Shell-Molting 规则 2（Verifier failure 归因惩罚）仍然触发
- `HumanAborted` 被 `runner.py` 捕获后，`stopped_early=True`，ShellMolting 和 SkillExtractor 仍会处理已收集的 Trace

---

## 8. 自主演化层（v0.2b + v0.3）

### 7.1 Shell-Molting 演化引擎

任务结束后，`ShellMolting.evolve()` 分析本次 Trace，按以下 5 条规则更新 `contribution_score`：

| 规则 | 触发条件 | Delta |
|------|----------|-------|
| 1 | Coral-Meeting winner | +0.10 |
| 2 | Verifier 判定 failure → 归因至最近上游非评估者 | −0.15 |
| 3 | Critic 判定 rejected → 归因至最近上游非评估者 | −0.10 |
| 4 | 任务 stopped_early → 全体参与 Agent 轻惩 | −0.05 |
| 5 | 更新 role_weights（winner +wins，其余仅 +total） | — |

`contribution_score` 下限为 0.0，通过 `AgentRepository.update_contribution()` 同步写入 SQLite。

归因逻辑由 `_find_upstream()` 实现：从触发评估的步骤往前倒序查找，跳过 verifier / critic / coral-meeting，取第一个生产者作为归因目标。

### 7.2 Skill 知识库（v0.3）

**提取**：任务结束后，`SkillExtractor.extract_and_save()` 对 `result=success` 的 Executor / Planner / Summarizer 步骤，调 LLM 用 ≤100 词总结推理技巧，写入 SQLite `skills` 表。每个 `(role, task_category)` 槽上限 10 条；LLM 返回 "N/A" 时跳过。

**注入**：`AgentFactory.create(profile, task_category)` 时，从 `skills` 表按 `(role, task_category)` 取 Top-3（按 usage_count 排序），拼接到 system_prompt 末尾。

---

## 9. 全局配置与 CLI

### 9.1 CrabShrimpConfig 开关总览

```python
# LLM
model: str                          # 默认 "claude-sonnet-4-6"
api_base: str | None                # LiteLLM 代理地址

# 资源
step_limit: int                     # 默认 50
token_budget: int                   # 默认 100_000

# 机制开关
coral_meeting_enabled: bool         # 默认 True
classify_enabled: bool              # 默认 True
trace_enabled: bool                 # 默认 True
resource_guard_enabled: bool        # 默认 True

# 隔离开关
context_isolation_enabled: bool     # 默认 True
workspace_isolation_enabled: bool   # 默认 True
exec_isolation_enabled: bool        # 默认 True

# v0.3 演化开关
skill_extraction_enabled: bool      # 默认 True
skill_injection_enabled: bool       # 默认 True
bench_threshold: float              # 默认 0.5

# Human-in-the-Loop
hitl_enabled: bool                  # 默认 False（总开关）
hitl_on_plan: bool                  # 默认 True（检查点 1：计划审核）
hitl_on_critical: bool              # 默认 True（检查点 2：共识审核）
hitl_on_verify_fail: bool           # 默认 True（检查点 3：Verifier 失败介入）

# 路径
trace_dir: str                      # 默认 "./traces"
db_path: str                        # 默认 "./xiabing.db"
```

所有选项均支持 `CRABSHRIMP_*` 环境变量覆盖，或通过 `CrabShrimpConfig.from_env()` 读取。

### 9.2 CLI 选项（`crabshrimp run`）

```bash
crabshrimp run --task "your task description" [OPTIONS]

  --model / -m          LLM 模型标识（LiteLLM 格式）
  --step-limit          最大步数
  --token-budget        最大 token 预算
  --trace-dir           Trace 文件保存目录
  --db-path             SQLite 数据库路径

  # 机制开关
  --no-coral-meeting    禁用 Coral-Meeting
  --no-classify         跳过任务分类（固定 general）
  --no-trace            禁用 JSONL trace 输出
  --no-resource-guard   禁用步数 / token 限制

  # 隔离开关
  --no-context-isolation    全 Agent 共享完整历史（调试用）
  --no-workspace-isolation  禁用工作空间隔离
  --no-exec-isolation       禁用子进程隔离

  # v0.3 演化开关
  --no-skill-extraction     禁用任务后 Skill 提取
  --no-skill-injection      禁用 Skill 注入 system prompt
  --bench-threshold FLOAT   拓扑筛选阈值（默认 0.5）

  # Human-in-the-Loop
  --hitl / --no-hitl        启用/禁用人在回路（默认关闭）
  --no-hitl-plan            启用 HITL 时跳过执行计划检查点
  --no-hitl-critical        启用 HITL 时跳过 Coral-Meeting 共识检查点
  --no-hitl-verify          启用 HITL 时跳过 Verifier 失败检查点
```

---

## 10. 测试覆盖

| 测试文件 | 覆盖模块 | 用例数 |
|----------|----------|--------|
| `test_models.py` | Message / TraceStep / AgentProfile | 3 |
| `test_resource_guard.py` | ResourceGuard | 3 |
| `test_verifier.py` | VerifierAgent 判定逻辑 | 2 |
| `test_orchestrator.py` | DragonKing 完整流程 | 1 |
| `test_isolation.py` | WorkspaceManager / SubprocessSandbox / Factory 注入 | 9 |
| `test_persistence.py` | AgentRepo / TaskRepo / MeetingRepo / Registry 跨任务保留 | 8 |
| `test_shell_molting.py` | ShellMolting 5 条规则 + 归因 + Critic 判定解析 | 12 |
| `test_skills.py` | SkillRepo / RoleWeightRepo / SkillExtractor / Factory 注入 | 13 |
| `test_hitl.py` | HumanGate 三个检查点 + approve / edit / abort + disabled 空操作 | 14 |
| **合计** | | **65** |

---

## 11. 架构成熟度判断

### 11.1 已落地能力

1. 多角色分工与中心调度闭环
2. Coral-Meeting 六步共识（含 SyncP2P 批评传递 + 立场修订）
3. 步数 + Token 预算控制 + 优雅停止
4. JSONL Trace 全程记录
5. SQLite 跨任务持久化（agent / task / meeting / skill / role_weights）
6. Shell-Molting 自动演化（contribution_score 动态更新）
7. Skill 提取与注入（LLM 蒸馏 + system_prompt 增强 + usage_count 反馈排序）
8. 拓扑调整（低胜率 Agent 退出会议）
9. 三层隔离（上下文 / 工作空间 / 执行环境）
10. 全机制可开关（config + CLI + 环境变量）
11. **Human-in-the-Loop**：三个检查点（计划审核 / 共识审核 / Verifier 失败介入），支持批准、修改、终止

### 11.2 仍处于预留或弱实现的部分

1. `DockerSandbox` 只是 stub，`exec_mode=docker` 会崩溃
2. 共识机制仍是"单轮审议"，未支持多轮迭代辩论
3. 状态同步是单机内存级，不支持跨进程 / 断点恢复
4. 进化树可视化尚未实现

---

## 12. 一句话总结

> 虾兵蟹将是一个"中心调度、角色分工、关键节点 P2P 协商、预算受控、过程可追踪、跨任务自主演化、人在回路可干预"的多智能体运行时原型，核心差异在于将 Agent 信誉、Skill 知识与拓扑结构都设计为可自动更新的变量，同时在关键节点为人工判断保留介入通道。
