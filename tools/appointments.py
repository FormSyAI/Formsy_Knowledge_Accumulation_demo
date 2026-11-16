"""工具：预约查询。"""

from hospital_api import HospitalAPI
from patient_store import resolve_authorized_patient


def list_appointments(patient_ref, date=None, department=None):
    patient_id = resolve_authorized_patient(patient_ref)
    rows = HospitalAPI().query_appointments(patient_id, date=date)["appointments"]
    appointments = [
        {field: row[field] for field in ("date", "time", "department", "status")}
        for row in rows
        if department is None or row["department"] == department
    ]
    return {"appointments": sorted(appointments, key=lambda row: (row["date"], row["time"]))}
