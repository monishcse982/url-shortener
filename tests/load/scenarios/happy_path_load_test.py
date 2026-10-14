import random
from urllib.parse import urlparse

from locust import HttpUser, constant, task

from tests.load.link_cases import LINK_CASES, VISIT_LIMIT, policy_for


class HappyPathMaxVisitsUser(HttpUser):
    wait_time = constant(1)

    @task
    def create_and_visit_link_mix(self):
        links: list[tuple[str, str, int | None]] = []
        cases = random.sample(LINK_CASES, k=len(LINK_CASES))

        for link_type, profile_name, ttl_seconds, max_visits in cases:
            case_name = f"{link_type}/{profile_name}"
            short_code = self._create_short_link(
                link_type=link_type,
                case_name=case_name,
                ttl_seconds=ttl_seconds,
                max_visits=max_visits,
            )
            if short_code is not None:
                links.append((short_code, case_name, max_visits))

        # Interleave visits across links instead of exhausting each in turn.
        for _ in range(VISIT_LIMIT):
            random.shuffle(links)
            for short_code, case_name, _ in links:
                self._visit(short_code, case_name)

        random.shuffle(links)
        for short_code, case_name, max_visits in links:
            expected_status = 410 if max_visits is not None else 302
            self._check_final_visit(short_code, case_name, expected_status)

    def _create_short_link(
        self,
        *,
        link_type: str,
        case_name: str,
        ttl_seconds: int,
        max_visits: int | None,
    ) -> str | None:
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
            if response.status_code != 200:
                response.failure(
                    f"Short link creation for {case_name} returned "
                    f"{response.status_code}: {response.text}"
                )
                return None

            try:
                shortened_url = response.json()["shortened_url"]
                short_code = urlparse(shortened_url).path.rstrip("/").split("/")[-1]
                if not short_code:
                    raise ValueError("response did not contain a short code")
            except (KeyError, TypeError, ValueError) as error:
                response.failure(f"Invalid shorten response for {case_name}: {error}")
                return None

            response.success()
            return short_code

    def _visit(self, short_code: str, policy_name: str) -> None:
        with self.client.get(
            f"/link/{short_code}",
            name=f"GET /link/{{short_code}} [{policy_name}]",
            catch_response=True,
            allow_redirects=False,
        ) as response:
            if response.status_code == 302:
                response.success()
            else:
                response.failure(
                    f"Visit for {policy_name} returned {response.status_code}"
                )

    def _check_final_visit(
        self, short_code: str, case_name: str, expected_status: int
    ) -> None:
        with self.client.get(
            f"/link/{short_code}",
            name=f"GET /link/{{short_code}} final [{case_name}]",
            catch_response=True,
            allow_redirects=False,
        ) as response:
            if response.status_code == expected_status:
                response.success()
            else:
                response.failure(
                    f"Expected {expected_status} for {case_name}, "
                    f"got {response.status_code}"
                )
