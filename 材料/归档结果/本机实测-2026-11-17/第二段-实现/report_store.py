"""检查报告本机留存：上传图片经本地 OCR 读取后，原文落盘供后续业务使用。

只有检查项目（items）会经工具提供给模型；patient_header（姓名、证件号等原文）
不出本机，图片本身由上传端存入本机并由 image_path 记录。
"""

import json
import os
import re
from datetime import datetime, timezone

from identifiers import IDENTIFIER, identifier_value
from patient_store import find_by_identifier, resolve_authorized_patient
from report_ocr import LocalOCR

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_reports")
REPORT_REF_RE = re.compile(r"(?<![A-Za-z0-9])RPT-[0-9]{4,}")


class ReportOwnershipError(PermissionError):
    """报告绑定的患者与当前查询对象不一致。"""


class UnknownReportError(KeyError):
    """report_ref 在本机没有对应报告。"""


def _header_patient_ref(patient_header):
    for match in IDENTIFIER.finditer(patient_header or ""):
        ref = find_by_identifier(identifier_value(match))
        if ref:
            return ref
    return None


def _next_report_ref(directory):
    numbers = [int(match[1]) for name in os.listdir(directory)
               if (match := re.fullmatch(r"RPT-([0-9]{4,})\.json", name))]
    return f"RPT-{max(numbers, default=0) + 1:04d}"


def ingest_report(patient_ref, upload_ref, image_path=None):
    """上传入口：校验报告归属后调用本地 OCR，原文存入本机并返回 report_ref。"""
    resolve_authorized_patient(patient_ref)
    try:
        raw = LocalOCR().read(upload_ref)
    except KeyError:
        raise UnknownReportError(upload_ref) from None
    owner_ref = _header_patient_ref(raw.get("patient_header", ""))
    if owner_ref is not None and owner_ref != patient_ref:
        raise ReportOwnershipError(f"报告头部身份不属于 {patient_ref}")
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_ref = _next_report_ref(REPORT_DIR)
    record = {
        "report_ref": report_ref,
        "patient_ref": patient_ref,
        "source_ref": upload_ref,
        "image_path": image_path,
        "verified": owner_ref == patient_ref,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "ocr": raw,
    }
    with open(os.path.join(REPORT_DIR, f"{report_ref}.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)
    return report_ref


def load_raw_report(report_ref):
    """按 report_ref 读取本机留存原文（供后续业务使用，不用于模型请求）。"""
    if not isinstance(report_ref, str) or not REPORT_REF_RE.fullmatch(report_ref):
        raise UnknownReportError(report_ref)
    try:
        with open(os.path.join(REPORT_DIR, f"{report_ref}.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise UnknownReportError(report_ref) from None
