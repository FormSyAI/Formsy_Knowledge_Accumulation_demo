"""工具：预约查询（按日期、科室筛选）。"""

from hospital_api import HospitalAPI
from patient_store import resolve_authorized_patient


def list_appointments(patient_ref, date=None, department=None):
    patient_id = resolve_authorized_patient(patient_ref)
    return HospitalAPI().query_appointments(patient_id, date=date, department=department)
