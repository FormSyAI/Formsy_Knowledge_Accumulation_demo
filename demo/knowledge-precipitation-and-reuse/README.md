# 演示（后半段）：人工纠正 → 知识沉淀 → 召回 → 第二模块复用

第一段在 [`../naive-agent-5of7/`](../naive-agent-5of7/README.md)：把裸 Agent 交给开发 AI，复现"脱敏只认连续数字"的缺陷
（2026-11-17 用 `tencent-cloud/deepseek-v4.1-flash` 复测，漏 5/7，与原始第 6、7 次一致）。

这一段讲**缺陷被发现之后**：人工评审 → 修复 → FormSy 采集与提炼 → 召回 → 第二个模块（报告解读）复用 → 独立探针验证。

## 0. 这一段要回答什么

- 沉淀出来的知识，能被召回到吗？
- 换一个模块、换一种数据来源（本地 OCR，而不是院内接口），开发 AI 会不会用上这些经验、并且不再犯同类错误？
- 这个结论能说到哪一步？（见第 6 节"边界"，很重要）

## 1. 人工纠正

评审在原实现里发现：脱敏正则只认连续数字，号码写成带空格 / 短横 / 全角时整段原文进了模型请求。
原文见 [`人工评审意见.md`](人工评审意见.md)。

修复后的实现**不在仓库工作区里**（2026-11-17 已从仓库移除，避免给第一段的开发 AI 递答案）。
用 [`预约查询-实现与修复.patch`](预约查询-实现与修复.patch) 从 `agent/` 复原即可：

```sh
cp -R agent /tmp/base && cd /tmp/base && git apply /path/to/预约查询-实现与修复.patch
```

它是：`IDENTIFIER` 覆盖全角与分隔符，`_redact` 在服务端统一脱敏，用户消息、工具参数与工具结果都过一遍。
（2026-11-17 实测：复原后的实现跑 `../naive-agent-5of7/变体探针.py` = **0/7 全脱敏**，与移除前一致。）

## 2. 知识沉淀（FormSy 真实提炼）

两条会话（首版实现 / 评审+修复）经 FormSy 采集后提炼出两份知识文档：

| 文档 | 要点 |
| --- | --- |
| [`知识文档/01-自然语言查询：服务端绑定身份并在模型边界脱敏.md`](知识文档) | 工具适配层只投影必要业务字段；身份在服务端解析；不采信模型返回的 `patient_ref` |
| [`知识文档/02-脱敏正则漏掉全角数字的修复.md`](知识文档) | 号码识别的边界不只是分隔符，还有**字符宽度**；回归要检查最终请求 |

这两份是 **2026-11-17 在正式 FormSy Server 上真实提炼出来的产物**，不是手写样例。

## 3. 召回（正式 Server）

[`项目知识召回.json`](项目知识召回.json) 就是本次喂给开发会话的召回结果，来自
`GET /api/v1/projects/{id}/knowledge/recall`，两组查询 × 两个视图：

| 查询 | 视图 | 命中 |
| --- | --- | --- |
| 工具返回 脱敏 模型请求 | knowledge / guidance | 2 / 2 |
| OCR 报告 身份字段 | knowledge / guidance | 1 / 1 |

召回返回的是**文档全文**，第一条即《自然语言查询：服务端绑定身份并在模型边界脱敏》。

## 4. 第二模块：报告解读

任务原文见 [`第二阶段任务.md`](第二阶段任务.md)。起点 = `agent/` ＋
[`预约查询-实现与修复.patch`](预约查询-实现与修复.patch)（复原出"预约查询已含修复"的状态）
＋ [`起始文件-report_ocr.py`](起始文件-report_ocr.py)（报告抬头里带**全角证件号**）。

开发会话的表现（完整事件流见 [`复用验证/开发会话事件.jsonl`](复用验证/开发会话事件.jsonl)）：

- 开场第一句就说要先读项目知识召回与医院数据要求，**第一条命令就是 `cat 项目知识召回.json`**；
- 方案（[`复用验证/方案.md`](复用验证/方案.md)）写明："服务端只挑选检查项目的 `name`、`value`、`unit`、`ref` 字段，
  图片、报告编号、患者抬头和其他 OCR 字段留在本机"；
- 实现见 [`复用验证/实现改动.patch`](复用验证/实现改动.patch)，它自己写的测试见 [`复用验证/它写的新测试.py`](复用验证/它写的新测试.py)。

## 5. 独立验证（不看它的测试）

[`复用验证/探针脚本.py`](复用验证/探针脚本.py) 注入等价 OCR 返回（抬头含全角证件号、半角证件号、手机号、姓名），
驱动**它自己的** `upload_report` 代码路径，读实际写出的模型请求：

| 检查项 | 结果 |
| --- | --- |
| 请求次数 | 1 |
| 原图是否留在本机 | true |
| 实际发给模型的 tool 内容 | 只有两项检查项目（`name`/`value`/`unit`/`ref`） |
| 全角证件号 / 半角证件号 / 手机号 / 姓名 / `patient_header` | **全部 false** |

原始输出见 [`复用验证/探针结果.json`](复用验证/探针结果.json)。

**2026-11-17 又当场重跑一轮**（同起点、同模型）：完整证件号（含全角）与完整手机号都没出境、
原始报告留在本机，事件流第 4 条命令就是 `cat 项目知识召回.json`；但它把**已脱敏的报告抬头**
也发给了模型，而归档那轮只投检查项目 —— 属于**部分复用**。细节、适配探针与逐项判读见
[`再跑一轮-2026-11-17/`](再跑一轮-2026-11-17/README.md)。

## 6. 边界（必须和结论一起讲）

- 这个模块"干净"，**不能单独证明是知识起了作用**：只投影检查项目的设计本身就把报告抬头挡在模型外面。
  同模块 3+3 对照（给 / 不给召回）两组都干净 → [`对照实验/A-复用对照实验-六轮无差别.md`](对照实验/A-复用对照实验-六轮无差别.md)。
- 知识有效性另有更强证据：在"已知会出错"的强诱导场景做 8 对 8，
  **给知识 0/8 泄露、不给知识 8/8 泄露** → [`对照实验/B-知识有效性对照实验-0对8.md`](对照实验/B-知识有效性对照实验-0对8.md)。
- 所以交差口径是：**知识确实有效，但只在风险真实存在的地方才看得出来。**

## 7. 自己跑一遍

```bash
# 1) 取起点：agent/ + 预约查询修复补丁 + OCR 桩件 + 召回结果 + 任务
git clone https://github.com/FormSyAI/Formsy_Knowledge_Accumulation_demo.git /tmp/fkad   # 只当材料来源
S=/tmp/fkad/demo/knowledge-precipitation-and-reuse
cp -R /tmp/fkad/agent /tmp/report-agent
cd /tmp/report-agent && git init -q && git add -A && git commit -qm "初始状态：裸 Agent"
git apply "$S/预约查询-实现与修复.patch" && git commit -aqm "预约查询（已修复）"
cp "$S/起始文件-report_ocr.py" report_ocr.py
cp "$S/项目知识召回.json" .
cp "$S/第二阶段任务.md" 任务.md
git add -A && git commit -qm "起点：预约查询已修复 + 报告解读任务"
```

> 克隆下来的 `/tmp/fkad` 只是**材料来源**：`复用验证/实现改动.patch`、`知识文档/`、`对照实验/` 都在里面，
> 等于把第二段的答案也带在身上。`-s workspace-write` 只限制写、不限制读，所以
> **别把它放在 `/tmp/report-agent` 旁边**，演示会话起来前把它挪走或删掉。

```bash

# 2) 隔离 CODEX_HOME（模型与第一段相同，见 ../naive-agent-5of7/README.md 的"用什么模型跑"）
mkdir -p /tmp/report-home && cp ~/.codex/auth.json /tmp/report-home/auth.json
cat > /tmp/report-home/config.toml <<'TOML'
model = "tencent-cloud/deepseek-v4.1-flash"
openai_base_url = "http://127.0.0.1:3425/backend-api/codex"
model_catalog_json = "/Users/lili/.codex/magpie-desktop-models.json"

[projects."/tmp/report-agent"]
trust_level = "trusted"
TOML

# 3) 跑第二阶段任务（新会话）
CODEX_HOME=/tmp/report-home codex exec --json -C /tmp/report-agent -s workspace-write \
  -m tencent-cloud/deepseek-v4.1-flash "$(cat /tmp/report-agent/任务.md)" > /tmp/report-events.jsonl

# 4) 独立验证：注入带身份字段的 OCR 返回，看实际模型请求
python3 "$S/复用验证/探针脚本.py" /tmp/report-agent
```

**不想跑模型也能验**：直接把当时那版实现套回起点仓库再跑探针——

```bash
cd /tmp/report-agent
git apply "$S/复用验证/实现改动.patch"
python3 "$S/复用验证/探针脚本.py" /tmp/report-agent   # 预期：全部 false
```

这条路径 2026-11-17 已实测通过（`patch applied` → 探针 `泄露检查` 全 false）。

> 探针的请求日志与原图目录默认写到系统临时目录（`report-probe-requests.jsonl` / `report-probe-reports`），
> 可以用环境变量 `PROBE_LOG`、`PROBE_REPORTS` 改。
