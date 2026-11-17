"""检查报告：上传登记与解读。

upload_report 由小程序上传接口调用（模型无权调用）；explain_report 是模型可调用的
工具，返回内容只包含脱敏后的报告头与检查项目，完整证件号留在本机。
"""

import re

from patient_store import resolve_authorized_patient
from privacy import redact
from report_ocr import LocalOCR
from report_store import ReportNotFound, load_report, save_report

REPORT_REF = re.compile(r"R[0-9]+")
ITEM_FIELDS = ("name", "value", "unit", "ref")


def upload_report(patient_ref, report_ref):
    """本地 OCR 读取报告并把原始内容留存本机，不访问外部网络。"""
    resolve_authorized_patient(patient_ref)
    try:
        raw = LocalOCR().read(report_ref)
    except KeyError:
        raise ReportNotFound(report_ref) from None
    save_report(report_ref, patient_ref, raw)
    return {"report_ref": report_ref}


def explain_report(patient_ref, report_ref):
    """返回可发给模型的报告内容：报告头脱敏，检查项目只留业务字段。"""
    resolve_authorized_patient(patient_ref)
    if not isinstance(report_ref, str) or not REPORT_REF.fullmatch(report_ref):
        raise ReportNotFound(report_ref)
    record = load_report(report_ref)
    if record["patient_ref"] != patient_ref:
        raise PermissionError(f"报告 {report_ref} 不属于 {patient_ref}")
    return {
        "report_ref": report_ref,
        "patient_header": redact(record["raw"]["patient_header"]),
        "items": [{field: item[field] for field in ITEM_FIELDS}
                  for item in record["raw"]["items"]],
    }
