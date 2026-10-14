from locust import LoadTestShape


class ConstantConcurrentUsers(LoadTestShape):
    def tick(self) -> tuple[int, int] | None:
        parsed_options = self.runner.environment.parsed_options

        if self.get_run_time() > parsed_options.pattern_duration_seconds:
            return None

        return parsed_options.concurrent_users, parsed_options.pattern_spawn_rate
