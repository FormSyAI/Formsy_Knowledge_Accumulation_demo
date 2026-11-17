# 知识沉淀演示仓库

这个仓库只有两样东西：**一个裸 Agent**（演示起点）和**一套案例材料**（演示前后的证据）。

| 路径 | 是什么 |
| --- | --- |
| [`agent/`](agent/) | 演示起点：客服 Agent 的初始形态，只有患者档案 / 用药 / 费用三个既有工具，**没有任何脱敏** |
| [`demo/`](demo/README.md) | 案例材料：前半段复现缺陷 + 后半段知识沉淀与复用 |

## 演示怎么跑

**演示机上只需要 `agent/` 这一个目录，不需要整个仓库。**

```sh
# 以下命令都在本仓库根目录执行
cp -R agent /tmp/demo-workspace
python3 demo/naive-agent-5of7/演示日期准备.py /tmp/demo-workspace   # 把夹具日期改成"今天/明天"，幂等
cd /tmp/demo-workspace && git init -q && git add -A && git commit -qm "初始状态：裸 Agent"
```

然后把 [`demo/naive-agent-5of7/起始任务.md`](demo/naive-agent-5of7/起始任务.md) 的原文交给一段**全新**的开发会话
（模型口径见该目录 README），跑完用
`python3 demo/naive-agent-5of7/变体探针.py /tmp/demo-workspace` 读数。

> ⚠️ **不要把本仓库整体 clone 到演示机上。** 这是案例材料仓库：里面有修复后的答案，
> 而且 git 历史里就有那次修复提交（`0b6553f 修复脱敏：覆盖全角号码与分隔符写法`）。
> `-s workspace-write` 只限制写、不限制读。演示机上只留从 `agent/` 复制出来的工作副本。

## 目录

| 路径 | 内容 |
| --- | --- |
| [`agent/`](agent/) | 裸 Agent（未脱敏的起点），自带它的 `README.md` / `任务.md` / `隐私与合规.md` |
| [`demo/README.md`](demo/README.md) | 两段材料索引 + **演示前检查清单** |
| [`demo/naive-agent-5of7/`](demo/naive-agent-5of7/README.md) | **前半段**：复现步骤、prompt、模型口径、7 种写法的探针、历史结果与本次复测 |
| [`demo/knowledge-precipitation-and-reuse/`](demo/knowledge-precipitation-and-reuse/README.md) | **后半段**：人工评审意见、两份知识文档、召回结果、复用验证、对照实验 |
| [`demo/预检问题回应.md`](demo/预检问题回应.md) | 演示预检挑出的 6 条意见，逐条核实、证据与处置 |

## 讲法（别讲过头）

- 前半段的缺陷形态是"**做了，但没做全**"：开发 AI 自己发现了合规冲突、也动手加了脱敏，
  但只认**连续数字**写法，带空格 / 短横 / 全角时原文照样进了模型请求（deepseek 轮实测漏 5/7）。
  **不要**讲成"AI 完全没想到要脱敏"——仓库里的复测证据会打脸。
- 缺陷是**概率性**的：同条件四次里三次出现、一次全拦；换模型分布会变。
  现场一次没复现，用 `demo/naive-agent-5of7/历史结果/` 说明分布，或当场重跑一轮。
- 后半段"第二个模块干净"**不能单独证明**知识起了作用；硬证据是强诱导场景的 8 对 8
  （给知识 **0/8** 泄露、不给知识 **8/8** 泄露）。

仓库内患者、手机号、证件号全部为**虚构合成数据**，不连接任何真实医院系统。
