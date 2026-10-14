from locust import LoadTestShape


class ConstantUsersPerSec(LoadTestShape):
    def tick(self) -> tuple[int, int] | None:
        parsed_options = self.runner.environment.parsed_options

        if self.get_run_time() > parsed_options.pattern_duration_seconds:
            return None

        users = max(
            parsed_options.target_rps // parsed_options.estimated_rps_per_user,
            1,
        )

        return users, parsed_options.pattern_spawn_rate
