"""工具：预约查询（按日期、科室筛选，返回已打码的患者信息）。"""

from datetime import date as _date

from hospital_api import HospitalAPI
from patient_store import public_patient, resolve_authorized_patient


def list_appointments(patient_ref, date=None, department=None):
    """查询预约；date 为 YYYY-MM-DD，department 为科室名。

    结果按日期、时间排序，编号顺序与患者看到的顺序一致。
    """
    if date is not None:
        try:
            date = _date.fromisoformat(str(date).strip()).isoformat()
        except ValueError:
            raise ValueError(f"日期格式应为 YYYY-MM-DD，收到 {date!r}")
    patient_id = resolve_authorized_patient(patient_ref)
    rows = HospitalAPI().query_appointments(patient_id, date=date)["appointments"]
    if department:
        rows = [row for row in rows if row["department"] == str(department).strip()]
    rows.sort(key=lambda row: (row["date"], row["time"]))
    return {"patient": public_patient(patient_ref), "appointments": rows}
