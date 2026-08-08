"""Teste de carga: quantas requisicoes simultaneas o servico aguenta antes
de degradar (latencia disparar ou erros aparecerem).

Uso:
    locust -f locustfile.py --host http://localhost:8000
    (abre UI em http://localhost:8089)

Ou headless:
    locust -f locustfile.py --host http://localhost:8000 \
        --headless --users 100 --spawn-rate 20 --run-time 30s
"""

from locust import HttpUser, task, between

KNOWN_USERS = [f"u_{i:04d}" for i in range(0, 500, 7)]  # amostra espalhada


class RecommendationUser(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(3)
    def get_recommendations_known_user(self):
        import random
        user_id = random.choice(KNOWN_USERS)
        self.client.get(f"/recommendations/{user_id}?top_n=10", name="/recommendations/[known]")

    @task(1)
    def get_recommendations_cold_start(self):
        self.client.get("/recommendations/u_9999?top_n=10", name="/recommendations/[cold_start]")

    @task(1)
    def health(self):
        self.client.get("/health")
