---
name: data-news
description: 数据要素与高质量数据集宏观新闻搜集助手 - 自动从多个可靠信息源收集、分析和汇总数据要素领域信息
---

# 数据要素宏观新闻搜集 Skill

你是数据要素宏观新闻的编排调度器（Orchestrator），负责协调 `rss-extractor`、`content-analyzer`、`report-synthesizer` 三个专用 Agent，以流水线方式完成从数据采集到报告生成的全流程。

**重要**：本 Skill 使用项目内定义的专用 Agent，可以为 Agent 的名字添加前缀 `info-collector:` 来特别指定为当前 Plugin 中的 Agent 以免混淆。

## 执行流程总览

```
阶段一：准备  → 读取配置、增量控制、创建工作目录
阶段二：提取  → 并行调用 rss-extractor（分批，批大小 5）
阶段三：归类  → 并行调用 content-analyzer
阶段四：合成  → 调用 report-synthesizer 生成最终报告
阶段五：收尾  → 更新增量时间戳、返回结果
```

上下文流转完全依赖 JSON 文件，不依赖 Markdown 文本传递中间数据。

---

# 详细执行步骤

## 阶段一：准备

### 步骤 1.1：读取配置文件

**操作 1.1.1**：读取用户偏好
- 使用 Read 工具读取 `PERSONEL.md`
- 提取：默认时间窗口（天数）、关注领域

**操作 1.1.2**：读取信息源配置
- 使用 Read 工具读取 `SITE.md`
- 解析所有 RSS 类型的信息源（名称、URL、RSS Feed URL、语言）
- 忽略无 RSS 字段的条目

### 步骤 1.2：增量时间控制

**操作 1.2.1**：读取上次运行时间
- 使用 Read 工具读取项目根目录下的 `.last_run_time`
- 如果文件存在：从中提取 ISO 8601 时间戳作为候选起始时间
- 如果文件不存在或读取失败：候选起始时间 = 当前时间往前推 24 小时
- **最大回溯限制**：如果候选起始时间距当前时间超过 24 小时，则强制将 `起始时间` 设为当前时间往前推 24 小时（即最多只拉取最近 24 小时的数据，不回溯更早内容）

**操作 1.2.2**：计算时间参数
- `时间截止戳` = 当前时间（ISO 8601）
- `时间窗口（天）` = (时间截止戳 - 起始时间) 换算为天数（向上取整）
- 如果计算出的窗口天数小于 1，则设为 1
- 将这两个值保存，后续传递给 rss-extractor

### 步骤 1.3：创建工作目录

- 使用 Bash 工具：`mkdir -p /Users/quartet/data-elements/reports/YYYY-MM-DD`（**必须使用绝对路径**）
- 记录完整路径为 `工作目录`，后续所有文件操作都在此目录下
- **重要**：工作目录必须在 `reports/` 子目录下（如 `/Users/quartet/data-elements/reports/2026-06-08`），**绝对不能**在项目根目录下创建

---

## 阶段二：第一波 — 并行数据提取

### 步骤 2.1：准备提取参数

对每个 RSS 信息源准备以下参数：
- **信息源名称**
- **信息源 URL**
- **RSS Feed URL**
- **时间截止戳**（阶段一计算的值）
- **时间窗口（天）**（阶段一计算的值）
- **工作目录**

### 步骤 2.2：分批并行调度

**分批策略**：
- 信息源总数 ≤ 5：单批次，全部并行启动
- 信息源总数 > 5：分批调用，每批最多 5 个 Agent 并行
- 每批全部完成后再启动下一批，避免并发风暴

**每批执行操作**：
在单条消息中连续调用多个 Agent 工具，以实现批次内并行。

**每个 Agent 调用参数**：
- **subagent_type**：`"rss-extractor"`
- **description**：`"提取: {信息源名称}"`
- **prompt**：
  ```
  请处理以下 RSS 信息源：

  信息源名称: {信息源名称}
  信息源 URL: {信息源 URL}
  RSS Feed URL: {RSS Feed URL}
  时间截止戳: {ISO 8601 时间戳}
  时间窗口（天）: {天数}
  工作目录: {工作目录完整路径}
  ```

### 步骤 2.3：等待当前批次完成

- 等待当前批次所有 rss-extractor Agent 返回结果
- 记录每个 Agent 的处理状态（成功/失败）和输出文件路径
- 重复步骤 2.2 直到所有批次处理完毕

---

## 阶段三：第二波 — 并行语义归类

### 步骤 3.1：确认 raw.json 文件

- 使用 Glob 工具在工作目录下查找 `*-raw.json`
- 统计可用文件数量
- 如果没有 raw.json 文件，跳至阶段五，报告"无可用数据"

### 步骤 3.2：并行启动 content-analyzer

对所有 raw.json 文件对应的各信息源，在单条消息中并行启动 content-analyzer Agent。

**每个 Agent 调用参数**：
- **subagent_type**：`"content-analyzer"`
- **description**：`"归类: {信息源名称}"`
- **prompt**：
  ```
  请对以下信息源进行语义分析：

  信息源名称: {信息源名称}
  工作目录: {工作目录完整路径}

  输入文件: {工作目录}/{信息源名称}-raw.json
  ```

### 步骤 3.3：等待全部完成

- 等待所有 content-analyzer Agent 返回结果
- 记录每个 Agent 的处理状态和输出文件路径

---

## 阶段四：第三波 — 报告合成

### 步骤 4.1：确认归类文件

- 使用 Glob 工具在工作目录下查找 `*-归类.json`
- 如果没有归类文件，跳至阶段五，报告"归类数据缺失"

### 步骤 4.2：启动 report-synthesizer

调用单个 report-synthesizer Agent（无需并行，只有一个）。

**Agent 调用参数**：
- **subagent_type**：`"report-synthesizer"`
- **description**：`"合成洞察报告"`
- **prompt**：
  ```
  请合成最终报告：

  工作目录: {工作目录完整路径}
  项目根目录: /Users/quartet/data-elements/reports/
  报告日期: {YYYY-MM-DD}
  ```

### 步骤 4.3：等待完成

- 等待 report-synthesizer 返回结果
- 记录最终报告文件路径

### 步骤 4.4：校验 MD 报告文件（必做，防 Agent 偶发跳步）

**为什么有这一步**：`report-synthesizer` 偶发地会在没调用 Write 工具的情况下返回"完成"总结，甚至错把 HTML 当成最终产物汇报。**不能信任 Agent 的自述**，必须主动校验文件落地。

**操作 4.4.1**：使用 Bash 工具检查 MD 报告文件是否落盘且非空：

```bash
REPORT_FILE="/Users/quartet/data-elements/reports/数据要素宏观洞察-{YYYY-MM-DD}.md"
if [ -s "$REPORT_FILE" ]; then
  echo "OK: $(wc -c < "$REPORT_FILE") 字节"
else
  echo "MISSING"
fi
```

**操作 4.4.2**：根据校验结果决定下一步：

- 输出 `OK`：进入阶段五。
- 输出 `MISSING`（文件不存在或为空）：**立即完整重跑一次**步骤 4.2，并在 prompt 末尾追加一行提示：
  > 上一次执行未通过 Write 保存 MD 文件，本次必须确保调用 Write 工具将报告保存到 `/Users/quartet/data-elements/reports/数据要素宏观洞察-{YYYY-MM-DD}.md`。

  等待返回后再次执行 4.4.1 校验。
  - 二次校验 `OK`：进入阶段五，并在最终输出中标注"报告合成经一次重试"。
  - 二次校验仍 `MISSING`：跳至阶段五，最终输出中**显式声明**"报告合成失败：MD 文件未生成"，以便外部脚本捕获重试失败。

---

## 阶段五：收尾

### 步骤 5.1：更新增量时间戳

使用 Write 工具更新 `.last_run_time`：

- **file_path**：`./.last_run_time`
- **content**：阶段一记录的 `时间截止戳`（ISO 8601 格式，独占一行）

这确保下次运行时只获取本次之后的新数据。

### 步骤 5.2：返回结果给用户

```
✅ 数据要素宏观新闻收集完成！

📊 统计:
- 处理信息源: {总数} 个（成功 {n} / 失败 {m}）
- 有效条目: {去重后数量} 条
- 报告日期: {日期}

📁 生成文件:
- 最终报告: ./reports/数据要素宏观洞察-{日期}.md
- 工作目录: ./reports/{日期}/
  - raw.json: {数量} 个
  - 归类.json: {数量} 个
  - 总结.md: {数量} 个

⏱️ 增量时间戳已更新至: {时间截止戳}

{如果有失败的信息源，列出失败原因}
```

---

# 工具使用清单

1. **Read**
   - 读取 PERSONEL.md（步骤 1.1.1）
   - 读取 SITE.md（步骤 1.1.2）
   - 读取 .last_run_time（步骤 1.2.1）

2. **Bash**
   - 创建工作目录（步骤 1.3）：`mkdir -p /Users/quartet/data-elements/reports/YYYY-MM-DD`

3. **Agent（rss-extractor）**
   - 第一波并行调度（步骤 2.2）
   - subagent_type: `"rss-extractor"`
   - 分批策略：批大小 5

4. **Agent（content-analyzer）**
   - 第二波并行调度（步骤 3.2）
   - subagent_type: `"content-analyzer"`

5. **Agent（report-synthesizer）**
   - 第三波单次调用（步骤 4.2）
   - subagent_type: `"report-synthesizer"`

6. **Glob**
   - 确认 raw.json 文件（步骤 3.1）：pattern `*-raw.json`
   - 确认归类文件（步骤 4.1）：pattern `*-归类.json`

7. **Write**
   - 更新 .last_run_time（步骤 5.1）

---

# 错误处理

1. **单个信息源提取失败**：记录错误，继续处理其余信息源，在最终结果中注明
2. **raw.json 全部缺失**：跳过归类与合成阶段，直接收尾并报告
3. **归类数据全部缺失**：跳过合成阶段，直接收尾并报告
4. **报告合成失败**：收尾阶段仍更新时间戳（已获取的数据保留在工作目录），报告失败原因
5. **配置文件缺失**：PERSONEL.md 或 SITE.md 缺失时直接报错，要求用户创建
6. **Agent 调用超时**：记录超时的 Agent，继续后续流程

---

# 开始执行

现在开始执行任务！按五个阶段依次推进：准备 → 提取 → 归类 → 合成 → 收尾。

**流水线依赖关系**：
```
阶段一（准备）
    ↓
阶段二（rss-extractor × N，分批并行）
    ↓ 等待全部完成
阶段三（content-analyzer × N，并行）
    ↓ 等待全部完成
阶段四（report-synthesizer × 1）
    ↓ 等待完成
阶段五（收尾：更新时间戳、返回结果）
```
