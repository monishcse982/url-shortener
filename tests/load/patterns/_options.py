from locust import events


@events.init_command_line_parser.add_listener
def add_load_pattern_options(parser) -> None:
    parser.add_argument(
        "--pattern-duration-seconds",
        type=int,
        env_var="LOCUST_PATTERN_DURATION_SECONDS",
        default=300,
        help="Total duration of the selected load pattern in seconds.",
    )
    parser.add_argument(
        "--pattern-spawn-rate",
        type=int,
        env_var="LOCUST_PATTERN_SPAWN_RATE",
        default=10,
        help="Users to spawn per second when changing load.",
    )
    parser.add_argument(
        "--target-users",
        type=int,
        env_var="LOCUST_TARGET_USERS",
        default=100,
        help="Target users for rampUsers.",
    )
    parser.add_argument(
        "--ramp-duration-seconds",
        type=int,
        env_var="LOCUST_RAMP_DURATION_SECONDS",
        default=300,
        help="Ramp duration for rampUsers.",
    )
    parser.add_argument(
        "--constant-users",
        type=int,
        env_var="LOCUST_CONSTANT_USERS",
        default=50,
        help="Fixed user count for constantUsers.",
    )
    parser.add_argument(
        "--concurrent-users",
        type=int,
        env_var="LOCUST_CONCURRENT_USERS",
        default=50,
        help="Fixed concurrent user count for constantConcurrentUsers.",
    )
    parser.add_argument(
        "--spike-users",
        type=int,
        env_var="LOCUST_SPIKE_USERS",
        default=200,
        help="User count during each spike.",
    )
    parser.add_argument(
        "--spike-duration-seconds",
        type=int,
        env_var="LOCUST_SPIKE_DURATION_SECONDS",
        default=10,
        help="How long each spike stays active.",
    )
    parser.add_argument(
        "--spike-frequency-seconds",
        type=int,
        env_var="LOCUST_SPIKE_FREQUENCY_SECONDS",
        default=60,
        help="Approximate time between spike starts.",
    )
    parser.add_argument(
        "--jitter-seconds",
        type=int,
        env_var="LOCUST_JITTER_SECONDS",
        default=10,
        help="Random plus/minus variance applied to spike frequency.",
    )
    parser.add_argument(
        "--initial-delay-seconds",
        type=int,
        env_var="LOCUST_INITIAL_DELAY_SECONDS",
        default=15,
        help="Delay before the selected pattern starts producing load.",
    )
    parser.add_argument(
        "--step-duration-seconds",
        type=int,
        env_var="LOCUST_STEP_DURATION_SECONDS",
        default=60,
        help="Duration of each step for stepUsers.",
    )
    parser.add_argument(
        "--step-users",
        type=int,
        env_var="LOCUST_STEP_USERS",
        default=50,
        help="Users added at each step for stepUsers.",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        env_var="LOCUST_MAX_USERS",
        default=250,
        help="Maximum users for stepUsers.",
    )
    parser.add_argument(
        "--target-rps",
        type=int,
        env_var="LOCUST_TARGET_RPS",
        default=100,
        help="Approximate target requests per second for constantUsersPerSec.",
    )
    parser.add_argument(
        "--estimated-rps-per-user",
        type=int,
        env_var="LOCUST_ESTIMATED_RPS_PER_USER",
        default=1,
        help="Estimated requests per second produced by one user.",
    )
