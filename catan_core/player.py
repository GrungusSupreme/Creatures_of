from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping

from .enums import DevelopmentCardType, ResourceType


@dataclass
class Player:
    player_id: int
    name: str
    resources: Counter = field(default_factory=Counter)
    development_cards: list[DevelopmentCardType] = field(default_factory=list)
    victory_points: int = 0
    settlements: set[int] = field(default_factory=set)
    cities: set[int] = field(default_factory=set)
    roads: set[int] = field(default_factory=set)

    def add_resource(self, resource: ResourceType, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        self.resources[resource] += amount

    def remove_resource(self, resource: ResourceType, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        if self.resources[resource] < amount:
            raise ValueError(f"Not enough {resource.value} to remove")
        self.resources[resource] -= amount

    def can_afford(self, cost: Mapping[ResourceType, int]) -> bool:
        return all(self.resources[resource] >= amount for resource, amount in cost.items())

    def spend_resources(self, cost: Mapping[ResourceType, int]) -> None:
        if not self.can_afford(cost):
            raise ValueError("Player cannot afford the required cost")
        for resource, amount in cost.items():
            self.resources[resource] -= amount
