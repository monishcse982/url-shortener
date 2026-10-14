from argparse import Namespace

from locust import LoadTestShape


def _parsed_options(shape: LoadTestShape) -> Namespace:
    runner = shape.runner
    assert runner is not None

    return runner.environment.parsed_options


class RampUsers(LoadTestShape):
    def tick(self) -> tuple[int, int] | None:
        run_time = self.get_run_time()
        parsed_options = _parsed_options(self)

        ramp_duration_seconds = parsed_options.ramp_duration_seconds
        target_users = parsed_options.target_users
        spawn_rate = parsed_options.pattern_spawn_rate

        if run_time > ramp_duration_seconds:
            return None

        users = int((run_time / ramp_duration_seconds) * target_users)

        return max(users, 1), spawn_rate
