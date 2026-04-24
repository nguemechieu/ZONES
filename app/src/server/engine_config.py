from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class EngineConfig:
    account_id: str = "demo"
    symbol: str = "EURUSD"
    ai_enabled: bool = True
    minimum_trade_score: float = 2.0
    min_confluence_count: int = 3
    machine_learning_min_samples: int = 20
    entry_preference: str = "middle"
    allowed_sessions: tuple[str, ...] = ("london", "new_york")
    temp_zone_min_thickness: float = 0.18
    temp_zone_max_thickness: float = 0.95
    main_zone_min_thickness: float = 0.22
    main_zone_max_thickness: float = 1.35
    require_confirmation_signal: bool = False
    require_htf_alignment: bool = False
    require_news_clearance: bool = False
    require_liquidity_target: bool = False
    fibonacci_levels: tuple[float, ...] = (0.382, 0.5, 0.618, 0.705, 0.79)
    fib_extension_levels: tuple[float, ...] = (1.272, 1.618, 2.0)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.allowed_sessions, list):
            self.allowed_sessions = tuple(str(item) for item in self.allowed_sessions)
        if isinstance(self.fibonacci_levels, list):
            self.fibonacci_levels = tuple(float(item) for item in self.fibonacci_levels)
        if isinstance(self.fib_extension_levels, list):
            self.fib_extension_levels = tuple(float(item) for item in self.fib_extension_levels)

    def to_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["allowed_sessions"] = tuple(self.allowed_sessions)
        values["fibonacci_levels"] = tuple(self.fibonacci_levels)
        values["fib_extension_levels"] = tuple(self.fib_extension_levels)
        return values
