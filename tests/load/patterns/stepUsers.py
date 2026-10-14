from locust import LoadTestShape


class StepUsers(LoadTestShape):
    def tick(self) -> tuple[int, int] | None:
        run_time = self.get_run_time()
        parsed_options = self.runner.environment.parsed_options

        if run_time > parsed_options.pattern_duration_seconds:
            return None

        step_number = int(run_time // parsed_options.step_duration_seconds) + 1
        users = min(step_number * parsed_options.step_users, parsed_options.max_users)

        return users, parsed_options.pattern_spawn_rate
