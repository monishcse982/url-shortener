import random

from locust import HttpUser, constant, task

from tests.load.link_cases import LINK_CASES, policy_for


class CreateShortLinkUser(HttpUser):
    wait_time = constant(1)

    @task
    def create_short_link(self):
        for link_type, profile_name, ttl_seconds, max_visits in random.sample(
            LINK_CASES, k=len(LINK_CASES)
        ):
            case_name = f"{link_type}/{profile_name}"
            payload = {
                "url": f"{self.host.rstrip('/')}/dummy-target",
                "ttl_seconds": ttl_seconds,
                "title": f"Load test {case_name}",
                "policy": policy_for(link_type),
            }
            if max_visits is not None:
                payload["max_visits"] = max_visits

            with self.client.post(
                "/link/",
                name=f"POST /link/ [{case_name}]",
                catch_response=True,
                json=payload,
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(
                        f"Creation of {case_name} link returned {response.status_code}"
                    )
