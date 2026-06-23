# loop_v3 vs 生产级 Agent（Claude Code / Cursor Hermes）全维度对比

## 演进轨迹回顾：loop_v1 → v2 → v3

| 版本 | 工具数 | 代码量 | 核心理念 |
|------|--------|--------|---------|
| v1 | 1 (时间) | 92 行 | 验证 tool-calling 通 |
| v2 | 4 (+读写/终端) | 194 行 | 通用工具 agent |
| v3 | 5 (+知识库) | 375 行 | RAG agent |

---

## 一、Loop 机制本身的差距

### 1.1 终止条件

loop_v3 的问题：LLM 可能在应该继续时错误地停止，也可能无限循环（调了工具但不收敛）。

生产级设计包含：
- 硬上限：max_turns（防无限循环）
- Token 预算上限：总消耗超过阈值 → 强制总结或终止
- 时间上限：单次请求的总 wall-clock 时间
- 收敛检测：连续 N 轮无实质进展 → 终止
- 用户中断：随时注入 stop 信号且优雅退出
- LLM 显式声明 FINISH：不允许 LLM 隐式决定终止，要求结构化信号

### 1.2 消息管理

loop_v3 的问题：永远 append 永不裁剪。上下文窗口有上限（DeepSeek 64K），超过后 API 直接报错。没有管理哪些信息值得保留。100 轮后成本爆炸。

生产级设计包含：

上下文压缩（Context Compaction）：
- 检测输入 token 接近模型上限（如 80%）
- 调用一个总结 LLM 把历史对话压缩为摘要
- 保留最近 N 轮的完整消息（滑动窗口）
- 结构化保留关键信息：文件操作记录、发现的事实、未完成任务

消息分层：
- system prompt（永远保留）
- 压缩后的历史摘要（1 条，定期更新）
- 最近 K 轮完整消息（K=5~10）
- 当前轮消息

工具结果截断策略：
- 第一次给完整（如果 < N token）
- 超过阈值 → 只给 head + tail + 行数统计
- 提供 read_more(offset, limit) 工具让 LLM 按需获取
- 对搜索结果只保留 top-K 的摘要

### 1.3 流式输出

loop_v3：无。用户等到最后才能看到结果。

生产级设计：
- LLM 响应流式传输（SSE / chunked）
- 工具调用也流式展示：显示"正在搜索..."、"找到 3 条结果"
- 工具输出实时打印（非阻塞）
- 支持流式中断：用户看到一半觉得不对，可以 abort
- 中断后仍保留已产生的结果（不丢上下文）

---

## 二、安全与权限（Claude Code 最核心的设计投入）

### 2.1 权限系统

loop_v3：terminal 工具 shell=True，LLM 可以执行任意命令。零限制。

Claude Code 的设计包含：

三级权限模型：
- allow：自动允许（如只读命令）
- deny：自动拒绝（如 rm -rf /）
- ask：弹出确认框给用户

权限规则的存储：
- 全局规则（~/.claude/settings.json）
- 项目规则（.claude/settings.json）
- 会话规则（本次生效）

权限匹配引擎：
- 精确匹配 + 通配符匹配
- 基于命令类别的快捷规则（所有读文件允许）
- 基于路径的规则（允许操作 /project/* 拒绝 /etc/*）

权限持久化：
- "记住此选择" → 写入规则文件
- 带时效的规则（本次会话 / 永久）

### 2.2 沙箱

loop_v3：无沙箱，agent 直接操作宿主机。

生产级设计：
- 文件系统沙箱：可访问目录白名单、只读vs读写挂载、禁止系统目录
- 网络沙箱：允许/禁止出站请求、域名白名单、禁止内网地址
- 进程沙箱：限制子进程数量、CPU/内存、Docker 容器隔离
- 命令危险检测：正则匹配危险模式（rm -rf, chmod 777, curl | bash），在发送给 shell 之前拦截

---

## 三、工具系统的差距

### 3.1 工具对比

| loop_v3 工具 | 对应生产级 | 差距 |
|-------------|-----------|------|
| read_file | Read | 无分页、无代码高亮、无行号、无图片/PDF 支持 |
| write_file | Write + Edit | 无 diff 级编辑（Edit 是精确字符串替换，不对整个文件重写，避免冲突） |
| terminal | Bash | 无沙箱、无描述字段、无后台运行、无超时可配置 |
| search_knowledge | 无对应 | RAG 搜索是亮点 |
| 无 | Glob / Grep | 代码搜索是 agent 最常用工具 |
| 无 | WebFetch / WebSearch | 联网能力 |
| 无 | TaskCreate / TaskUpdate | 任务拆解与追踪 |
| 无 | AskUserQuestion | 阻塞向用户澄清需求 |
| 无 | NotebookEdit | 结构化文档编辑 |
| 无 | Agent（子 agent 生成） | 并行多 agent |

### 3.2 关键缺失工具详解

#### Edit（精确替换）vs Write（全量覆盖）

Claude Code 最精妙的设计之一：
- Write：覆盖整个文件 → 简单但危险（并发冲突、丢别人改动）
- Edit：精确字符串替换 → 安全但复杂（需要唯一匹配）

Edit 的实现难点：
- old_string 必须唯一匹配（否则拒绝编辑）
- 支持 replace_all 批量替换
- 需要处理缩进/空白字符的精确匹配
- 与文件系统版本对比，检测并发修改
- 返回精确的 diff 给 LLM 确认

#### 搜索工具（Grep / Glob）

Agent 最常做的事不是写代码，是找代码：
- Glob：按文件名模式找文件，如 glob("**/*.py")
- Grep：按内容搜索，如 grep("pattern", path="src/", include="*.py")
- 结果截断（最多返回 N 条，告诉 LLM 还有更多）
- 排除 .git / node_modules 等目录
- 支持正则
- 返回行号（后续 Edit 需精确定位）

#### 多模态工具
- 图片读取：Read 支持 PNG/JPG，返回视觉描述
- PDF 读取：按页范围读取
- Notebook 读取：按 cell 展示

---

## 四、System Prompt 的差距

loop_v3 的 system prompt：2 句话，约 50 字。

生产级 system prompt 包含数千行内容：
- 角色定义 + 能力边界
- 工具使用规范（每个工具何时用、何时不用）
- 代码风格要求（match surrounding code）
- 权限模型说明
- 错误处理策略
- 沟通规范（不叙述不会执行的选项）
- Context management 规则（什么时候 summarize）
- 文件读写规范（Read before Edit，不在内存里猜文件内容）
- Git 规范（commit message 格式、Co-Authored-By）
- 子 agent 使用规范（何时 spawn，何时不 spawn）
- Plan mode 规范
- 输出格式要求
- 安全边界

---

## 五、多 Agent 协作 / 并行

loop_v3：单进程、单线程、单 agent、while True 串行。

生产级设计：

子 Agent 生成（Agent Spawning）：
- 主 Agent 决定"这个任务需要拆成 3 个子任务"
- 每个子 agent 独立上下文窗口
- 子 agent 返回结构化结果
- 主 agent 合并结果继续

Agent 类型分化：
- Explore agent：只读搜索，不写文件
- Plan agent：只出方案，不执行
- General agent：全能力
- 每个类型的工具集不同（最小权限原则）

并行执行策略：
- pipeline()：流水线并行（默认）
- parallel()：Barrier 并行
- 并发控制（最多 N 个 agent 同时运行）

隔离：
- Worktree 隔离：子 agent 在独立 git worktree 中操作
- 文件系统隔离：防止并行 agent 互相覆盖文件

---

## 六、执行环境与状态管理

### 6.1 项目感知

loop_v3：硬编码路径，无项目上下文。

生产级设计：
- 自动检测项目根目录（.git / 配置文件）
- 读取项目配置文件
- 构建项目上下文：技术栈、目录结构、编码规范
- 所有相对路径基于项目根目录

### 6.2 持久化记忆

Claude Code 记忆系统：
- 分层记忆：user（身份/偏好）、feedback（纠正过的行为）、project（项目信息）、reference（外部资源）
- 记忆生命周期：写入（Markdown + frontmatter）、索引（MEMORY.md）、召回（每次对话加载）、过期/合并
- 记忆关联：wiki-link 语法链接相关记忆

### 6.3 会话恢复

loop_v3：程序结束 = 一切丢失。

生产级设计：
- 会话持久化：完整 messages 序列化到磁盘
- 会话恢复：下次启动加载历史
- 会话列表：多个独立会话并存
- 会话分支：从某个检查点分叉
- JSONL 格式：每行一个事件，可增量追加

---

## 七、任务规划与拆解

loop_v3：用户问一个问题 → agent 搜索 → 回答（线性、单一目标）

生产级设计包含：

显式规划阶段（Plan Mode）：
- 进入计划模式：用户审批方案后再执行
- 计划包含：步骤列表、涉及文件、风险点
- 计划可修改：用户提出调整 → 更新计划 → 再审批

任务追踪系统（TaskCreate/TaskUpdate）：
- 任务状态：pending → in_progress → completed
- 任务依赖：Task B 依赖 Task A 完成
- 进度可视化：spinner + 当前任务描述
- 动态调整：执行中发现新任务 → 追加到列表

复杂任务分解模式：
- 用户："重构认证系统"
- Agent：拆成 7 个子任务，逐个执行，记录每步结果

---

## 八、错误处理与韧性

### loop_v3：单一 try-except 返回错误字符串

### 生产级设计包含：

分层错误处理：
- 工具级：每个工具自己的异常处理
- Loop 级：工具调用失败不影响整个 loop
- API 级：网络错误→重试，模型过载→降级
- 系统级：OOM / 进程被杀→优雅关闭

重试策略：
- 指数退避（1s → 2s → 4s → 8s）
- 最大重试次数
- 可重试错误 vs 不可重试错误的区分
  - 429 Rate Limit → 重试
  - 503 Service Unavailable → 重试 + 切换 provider
  - 400 Bad Request → 不重试（请求本身有问题）
  - 401 Unauthorized → 不重试（密钥问题）
- 重试时常数抖动（jitter）防止惊群

熔断（Circuit Breaker）：
- 连续失败 N 次 → 暂停调用该工具
- 冷却期后尝试恢复
- 降级策略（用简单方法替代复杂工具）

模型 Fallback 链：
- 尝试 claude-opus-4-8 → 失败 → 尝试 claude-sonnet-4-6 → 失败 → 尝试 deepseek-chat → 失败 → 返回缓存答案

部分成功处理：
- LLM 调了 3 个工具，2 个成功 1 个失败
- 成功的结果照常返回，失败的结果标注错误
- LLM 基于部分结果继续判断

---

## 九、可观测性

### loop_v3：裸 print()

### 生产级设计：

结构化日志（JSON 格式）：
- timestamp, session_id, turn, event, tool, args, duration_ms, result_size, trace_id

全链路追踪（OpenTelemetry）：
- 每个 API 调用生成 span
- 每个工具调用是子 span
- traceId 贯穿整个对话
- 可视化：Grafana / Jaeger

LLM 专项可观测（LangFuse / LangSmith）：
- 每次 LLM 调用的 prompt/completion
- Token 用量和成本
- 延迟分布（P50/P95/P99）
- 错误率按工具/模型分组
- 用户反馈收集（赞/踩）

调试模式：
- --verbose：打印所有中间状态
- --dry-run：只展示会做什么，不执行
- replay：用历史日志重放，调试 bug

---

## 十、用户体验

loop_v3：终端里运行一个 Python 脚本，无交互。

生产级设计：

交互模式：
- REPL 循环：用户持续输入，agent 持续响应
- 多轮对话：保持上下文
- /slash 命令：/help, /clear, /plan, /memory
- 快捷键绑定

输出呈现：
- Markdown 渲染（不是纯文本）
- 代码块语法高亮
- 工具调用进度指示器（spinner）
- 折叠长输出（用户可展开）
- Diff 可视化（+/- 行）

输入能力：
- 多行输入
- 粘贴文件路径 → 自动读取
- @file 引用语法
- 管道输入（echo "..." | agent）

中断与控制：
- Ctrl+C 中断当前操作
- 中断后可选：继续 / 回退 / 放弃
- /undo 撤销上一次文件操作

---

## 十一、平台与集成

loop_v3：一个 .py 文件，本地终端运行。

生产级设计：

多端运行：
- CLI 终端（主力）
- IDE 插件（VS Code / JetBrains）
- Web 界面（claude.ai/code）
- API 服务（HTTP endpoint）

多平台：
- macOS / Linux / Windows
- 包管理器分发（npm / brew / pip）
- 自动更新

集成：
- Git 深度集成（commit, PR, diff, blame）
- GitHub/GitLab API（Issue, PR review）
- MCP（Model Context Protocol）连接外部工具
- CI/CD 流水线（作为 check 的一步）

多用户 / 团队：
- 共享配置（团队 rules）
- 共享记忆（团队 knowledge base）
- 用量统计（按成员/按项目）

---

## 十二、从 loop_v3 出发的升级路线图（按投入产出比排序）

### 第一优先级：Loop 本身的鲁棒性（1-2 周）

1. 消息窗口管理
   - 估算 token 数（tiktoken）
   - 接近上限时触发压缩（用 LLM 总结历史）
   - 保留最近 5 轮完整消息

2. 安全基础
   - 危险命令黑名单（至少拦截 rm -rf / sudo / curl | bash）
   - 可访问目录白名单
   - 至少实现 ask/allow/deny 三级中的前两级

3. 工具增强
   - Grep 工具（代码搜索是 agent 最高频操作）
   - Glob 工具（按文件名模式找文件）
   - Edit 工具（精确替换，替代全量 write）
   - read_file 加入行号和分页

4. 错误韧性
   - API 调用加重试（指数退避）
   - 熔断器（某个工具连续失败 → 禁用）
   - 至少 2 个模型 provider 做 fallback

### 第二优先级：交互与体验（2-4 周）

5. 流式输出
   - LLM 响应 SSE 流式打印
   - 工具调用过程实时展示

6. REPL 交互
   - 替代硬编码的 user message
   - 多轮对话循环
   - Ctrl+C 中断处理

7. System Prompt 工程
   - 写 500+ 行的详细 system prompt
   - 定义工具使用规范
   - 定义代码风格
   - 定义错误处理策略

8. 结构化日志
   - 替换 print 为 structlog
   - 每次 API 调用记录耗时/token
   - 写入 JSONL 文件

### 第三优先级：多 Agent + 规划（4-8 周）

9. 任务系统
   - TaskCreate / TaskUpdate
   - 进度追踪
   - 依赖管理

10. 子 Agent 生成
    - 主 Agent 拆解任务 → 并行发子 agent
    - 子 agent 独立上下文
    - 结果合并

11. 权限系统完整实现
    - 持久化规则文件
    - 通配符匹配
    - 分层规则（global / project / session）

### 第四优先级：平台化（8+ 周）

12. 会话持久化
13. 记忆系统
14. MCP 协议支持
15. IDE 插件 / Web 界面
16. 团队协作

---

## 总结：核心差距一句话版

| 维度 | loop_v3 | 生产级 Agent |
|------|---------|-------------|
| 安全 | 无任何限制 | 3 级权限 + 沙箱 + 命令过滤 |
| 上下文 | 无限 append | 压缩 + 滑动窗口 + 预算管理 |
| 工具 | 5 个基础工具 | 15+ 专用工具（搜索/编辑/子 agent） |
| 并行 | 串行 while True | 多 agent 并发 + pipeline |
| 容错 | try-except 兜底 | 重试/熔断/降级/fallback |
| 可观测 | print() | 结构化日志 + 全链路追踪 |
| 交互 | 硬编码单轮 | REPL + 流式 + 中断 + 断点续传 |
| 记忆 | 无 | 分层持久化记忆系统 |
| System Prompt | 2 句话 | 数千行宪法级规范 |

核心结论：loop_v3 作为 Agent 内核验证非常成功。375 行 Python 就可以让 LLM 搜索知识库并回答问题。但成为能被广泛使用的 agent 产品，上面那些非功能性能力占了真实工作量的 80% 以上。Claude Code 的代码库中，核心 loop 可能只占 5%，剩下 95% 全在这些维度里。
