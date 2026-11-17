"""工具：预约查询（支持按日期、科室筛选）。"""

from hospital_api import HospitalAPI
from patient_store import resolve_authorized_patient
from privacy import mask_patient

APPOINTMENT_FIELDS = ("appointment_id", "date", "time", "department", "status")


def list_appointments(patient_ref, date=None, department=None):
    patient_id = resolve_authorized_patient(patient_ref)
    result = HospitalAPI().query_appointments(patient_id, date=date, department=department)
    return {
        "patient": mask_patient(result["patient"]),
        "appointments": [
            {field: row[field] for field in APPOINTMENT_FIELDS if field in row}
            for row in result["appointments"]
        ],
    }
