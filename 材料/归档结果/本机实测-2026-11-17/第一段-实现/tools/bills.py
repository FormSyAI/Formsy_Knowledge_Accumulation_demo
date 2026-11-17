"""工具：费用明细查询（已上线）。"""

from hospital_api import HospitalAPI
from patient_store import resolve_authorized_patient
from privacy import mask_patient


def list_bills(patient_ref):
    patient_id = resolve_authorized_patient(patient_ref)
    result = HospitalAPI().list_bills(patient_id)
    return {"patient": mask_patient(result["patient"]), "bills": result["bills"]}
