import uuid

from locust import HttpUser, between, task


class ChatApiUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.session_id = str(uuid.uuid4())

    @task
    def chat(self) -> None:
        payload = {
            "text": "我今天要冲刺一道算法题，请先帮我拆解执行步骤并判断优先级。"
        }
        headers = {"x-session-id": self.session_id}
        self.client.post("/api/v1/chat", json=payload, headers=headers, name="/api/v1/chat")
