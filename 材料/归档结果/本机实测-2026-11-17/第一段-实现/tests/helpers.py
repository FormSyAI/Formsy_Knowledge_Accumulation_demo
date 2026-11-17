"""测试辅助：记录发往模型的消息并按脚本返回响应。"""


class RecordingModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def send(self, messages):
        self.requests.append(messages)
        if not self.responses:
            raise AssertionError("RecordingModel 的脚本响应已用完")
        return self.responses.pop(0)
