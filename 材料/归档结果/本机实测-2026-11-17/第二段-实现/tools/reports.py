"""工具：检查报告解读（只提供业务项目，原文身份信息不出本机）。"""

from patient_store import resolve_authorized_patient
from report_store import ReportOwnershipError, load_raw_report


def read_report(patient_ref, report_ref):
    resolve_authorized_patient(patient_ref)
    record = load_raw_report(report_ref)
    if record["patient_ref"] != patient_ref:
        raise ReportOwnershipError(f"报告 {report_ref} 不属于 {patient_ref}")
    return {"report_ref": report_ref, "items": [dict(item) for item in record["ocr"]["items"]]}
