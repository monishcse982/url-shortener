import random
from urllib.parse import urlparse

from locust import HttpUser, constant, task

from tests.load.link_cases import LINK_CASES, policy_for


class VisitShortLinkUser(HttpUser):
    wait_time = constant(1)

    def on_start(self) -> None:
        self.short_codes = {
            f"{link_type}/{profile_name}": self._create_short_link(
                link_type, profile_name, ttl_seconds, max_visits
            )
            for link_type, profile_name, ttl_seconds, max_visits in LINK_CASES
        }

    @task
    def visit_short_link(self):
        for link_type, profile_name, ttl_seconds, max_visits in random.sample(
            LINK_CASES, k=len(LINK_CASES)
        ):
            case_name = f"{link_type}/{profile_name}"
            short_code = self.short_codes[case_name]
            with self.client.get(
                f"/link/{short_code}",
                name=f"GET /link/{{short_code}} [{case_name}]",
                catch_response=True,
                allow_redirects=False,
            ) as response:
                if response.status_code == 302:
                    response.success()
                elif response.status_code == 410:
                    response.success()
                    self.short_codes[case_name] = self._create_short_link(
                        link_type, profile_name, ttl_seconds, max_visits
                    )
                else:
                    response.failure(
                        f"{case_name} link {short_code} returned {response.status_code}"
                    )

    def _create_short_link(
        self,
        link_type: str,
        profile_name: str,
        ttl_seconds: int,
        max_visits: int | None,
    ) -> str:
        case_name = f"{link_type}/{profile_name}"
        payload = {
            "url": f"{self.host.rstrip('/')}/dummy-target",
            "ttl_seconds": ttl_seconds,
            "title": f"Load test {case_name}",
            "policy": policy_for(link_type),
        }
        if max_visits is not None:
            payload["max_visits"] = max_visits

        response = self.client.post(
            "/link/",
            name=f"POST /link/ setup [{case_name}]",
            json=payload,
        )
        response.raise_for_status()

        shortened_url = response.json()["shortened_url"]
        return urlparse(shortened_url).path.rstrip("/").split("/")[-1]
