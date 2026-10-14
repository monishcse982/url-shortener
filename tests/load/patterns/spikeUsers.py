import random

from locust import LoadTestShape


class SpikeUsers(LoadTestShape):
    def __init__(self) -> None:
        super().__init__()
        self.next_spike_at: float | None = None
        self.spike_until: float | None = None

    def tick(self) -> tuple[int, int] | None:
        run_time = self.get_run_time()
        parsed_options = self.runner.environment.parsed_options

        if self.next_spike_at is None:
            self.next_spike_at = parsed_options.initial_delay_seconds

        if run_time > parsed_options.pattern_duration_seconds:
            return None

        if run_time < parsed_options.initial_delay_seconds:
            return 0, 1

        if self.spike_until is not None and run_time < self.spike_until:
            return parsed_options.spike_users, parsed_options.spike_users

        if run_time >= self.next_spike_at:
            self.spike_until = run_time + parsed_options.spike_duration_seconds
            jitter = random.uniform(
                -parsed_options.jitter_seconds,
                parsed_options.jitter_seconds,
            )
            self.next_spike_at = (
                run_time + parsed_options.spike_frequency_seconds + jitter
            )
            return parsed_options.spike_users, parsed_options.spike_users

        return 0, parsed_options.spike_users
