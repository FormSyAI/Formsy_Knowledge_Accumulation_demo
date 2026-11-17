# 患者小程序客服 Agent（本机演示）

医院患者小程序后端。患者用自然语言提问，服务端调用外部模型理解问题、选择工具并组织回答。

## 患者身份的判定方式（本项目已确定）

小程序不以账号体系区分患者，而是**以手机号或身份证号作为患者身份的唯一键**：

- 患者进入小程序时输入本人手机号或身份证号
- 系统据此确定"当前是谁"，以及可查看的已授权家属
- 同一手机号/证件号始终对应同一位患者

代码见 `patient_store.py`。

## 模块

- `patient_store.py`：身份唯一键（手机号 / 身份证号）、授权关系与院内 ID
- `hospital_api.py`：院内业务接口（工作站风格）
- `identifiers.py`：手机号/证件号识别、宽度归一化与脱敏（查找患者与模型边界共用）
- `tools/`：模型可调用的工具适配层（患者档案、用药记录、费用明细、检查报告）
- `report_store.py`：检查报告上传入库：本地 OCR 读取后原文留存本机，返回 `report_ref`
- `service.py`：客服 Agent 主流程（工具调用 → 模型请求）
- `model_client.py`：模型客户端；本机演示写本地日志，不访问外网

## 现有工具

`tools/` 下的工具已经在线运行，客服 Agent 通过 `service.py` 的 `TOOLS` 注册表调用它们。

## 检查报告解读（上传 → 本地 OCR → 通俗解释）

1. 小程序上传报告图片后，后端调用 `report_store.ingest_report(patient_ref, upload_ref, image_path=...)`：
   由本地部署的 `report_ocr.LocalOCR` 读取内容，**原文（含姓名、证件号等 `patient_header`）
   只写入本机 `local_reports/<report_ref>.json`**，供后续业务使用；同时用报告头的证件号/手机号
   核对报告归属，与上传患者不符则拒绝入库。
2. 后端把 `report_ref` 交给客服 Agent：`agent.answer("帮我解释这份检查报告", report_ref=report_ref)`；
   消息里带报告编号时服务端也会自行解析。
3. Agent 通过 `tools/reports.py::read_report` 读取报告，只把检查项目（名称/数值/单位/参考范围）
   发给外部模型；`patient_header` 原文不出本机，且发往模型的所有内容仍统一过
   `identifiers.redact`（完整手机号、完整证件号不出现，含全角写法）。模型用通俗中文解释
   每项指标及参考范围，并提醒以医生意见为准。

`patient_ref`、`report_ref` 均由服务端解析/注入，模型只能选择工具，不能指定查询对象或报告编号。

```sh
python3 -m unittest discover -v
```

患者与联系方式均为虚构测试数据。
