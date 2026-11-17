"""工具：患者档案查询（已上线）。"""

from hospital_api import HospitalAPI
from patient_store import resolve_authorized_patient
from privacy import mask_patient


def patient_profile(patient_ref, field=None):
    patient_id = resolve_authorized_patient(patient_ref)
    patient = mask_patient(HospitalAPI().patient_profile(patient_id)["patient"])
    if field:
        return {field: patient.get(field)}
    return {"patient": patient}
