"""本地 OCR：读取检查报告图片，输出纯文本结构化结果（本机部署，不上传外部网络）。"""

REPORTS = {
    "R1": {
        "patient_header": "姓名：张三丰(虚构)　证件号：３１０１０１１９８５１２０６１２３４　性别：男　年龄：36",
        "items": [
            {"name": "空腹血糖", "value": "6.8", "unit": "mmol/L", "ref": "3.9-6.1"},
            {"name": "总胆固醇", "value": "5.2", "unit": "mmol/L", "ref": "<5.2"},
        ],
    },
}


class LocalOCR:
    def read(self, report_ref):
        report = REPORTS[report_ref]
        return {"patient_header": report["patient_header"], "items": report["items"]}
