from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from .enums import ResourceType


@dataclass
class Vertex:
    vertex_id: int
    building_owner: int | None = None
    building_level: int = 0  # 0 = none, 1 = settlement, 2 = city
    adjacent_vertices: set[int] = field(default_factory=set)
    adjacent_edges: set[int] = field(default_factory=set)
    touching_hexes: set[int] = field(default_factory=set)

    @property
    def occupied(self) -> bool:
        return self.building_owner is not None and self.building_level > 0


@dataclass
class Edge:
    edge_id: int
    v1: int
    v2: int
    road_owner: int | None = None
    touching_hexes: set[int] = field(default_factory=set)

    @property
    def occupied(self) -> bool:
        return self.road_owner is not None


@dataclass
class Hex:
    hex_id: int
    q: int
    r: int
    resource: ResourceType
    token: int | None
    vertex_ids: tuple[int, int, int, int, int, int]
    edge_ids: tuple[int, int, int, int, int, int]
    neighbor_hex_ids: set[int] = field(default_factory=set)


@dataclass
class Port:
    port_id: int
    edge_id: int
    vertex_ids: tuple[int, int]
    rate: int
    resource: ResourceType | None = None


class Board:
    _AXIAL_DIRECTIONS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))

    def __init__(
        self,
        radius: int = 2,
        seed: int | None = None,
        custom_ports: list[dict[str, Any]] | None = None,
    ):
        if radius < 1:
            raise ValueError("radius must be >= 1")

        self.radius = radius
        self.seed = seed
        self.hexes: dict[int, Hex] = {}
        self.vertices: dict[int, Vertex] = {}
        self.edges: dict[int, Edge] = {}
        self.ports: dict[int, Port] = {}
        self._coords_to_hex_id: dict[tuple[int, int], int] = {}

        self._generate(custom_ports)

    def _generate(self, custom_ports: list[dict[str, Any]] | None = None) -> None:
        rng = random.Random(self.seed)

        coords: list[tuple[int, int]] = []
        for q in range(-self.radius, self.radius + 1):
            r1 = max(-self.radius, -q - self.radius)
            r2 = min(self.radius, -q + self.radius)
            for r in range(r1, r2 + 1):
                coords.append((q, r))

        resources = self._build_resource_list(len(coords), rng)
        tokens = self._build_token_list(len(coords), rng)

        vertex_lookup: dict[tuple[float, float], int] = {}
        edge_lookup: dict[tuple[int, int], int] = {}

        for hex_index, (q, r) in enumerate(coords):
            center_x = math.sqrt(3) * (q + r / 2)
            center_y = 1.5 * r

            v_ids: list[int] = []
            for corner in range(6):
                angle = math.radians(60 * corner - 30)
                corner_x = round(center_x + math.cos(angle), 6)
                corner_y = round(center_y + math.sin(angle), 6)
                key = (corner_x, corner_y)

                if key not in vertex_lookup:
                    vertex_id = len(self.vertices)
                    vertex_lookup[key] = vertex_id
                    self.vertices[vertex_id] = Vertex(vertex_id=vertex_id)
                v_ids.append(vertex_lookup[key])

            e_ids: list[int] = []
            for i in range(6):
                a = v_ids[i]
                b = v_ids[(i + 1) % 6]
                edge_key = tuple(sorted((a, b)))

                if edge_key not in edge_lookup:
                    edge_id = len(self.edges)
                    edge_lookup[edge_key] = edge_id
                    self.edges[edge_id] = Edge(edge_id=edge_id, v1=edge_key[0], v2=edge_key[1])

                e_id = edge_lookup[edge_key]
                e_ids.append(e_id)

                self.vertices[a].adjacent_vertices.add(b)
                self.vertices[b].adjacent_vertices.add(a)
                self.vertices[a].adjacent_edges.add(e_id)
                self.vertices[b].adjacent_edges.add(e_id)

            resource = resources[hex_index]
            token = None if resource == ResourceType.WASTELAND else tokens.pop()

            hex_obj = Hex(
                hex_id=hex_index,
                q=q,
                r=r,
                resource=resource,
                token=token,
                vertex_ids=tuple(v_ids),
                edge_ids=tuple(e_ids),
            )
            self.hexes[hex_index] = hex_obj
            self._coords_to_hex_id[(q, r)] = hex_index

            for vertex_id in v_ids:
                self.vertices[vertex_id].touching_hexes.add(hex_index)
            for edge_id in e_ids:
                self.edges[edge_id].touching_hexes.add(hex_index)

        for hex_obj in self.hexes.values():
            for dq, dr in self._AXIAL_DIRECTIONS:
                neighbor_coords = (hex_obj.q + dq, hex_obj.r + dr)
                neighbor_id = self._coords_to_hex_id.get(neighbor_coords)
                if neighbor_id is not None:
                    hex_obj.neighbor_hex_ids.add(neighbor_id)

        self._assign_ports(rng)
        if custom_ports is not None:
            self.configure_ports(custom_ports)

    def _assign_ports(self, rng: random.Random) -> None:
        coastal_edges = [
            edge
            for edge in self.edges.values()
            if len(edge.touching_hexes) == 1
        ]
        coastal_edges.sort(key=lambda edge: edge.edge_id)
        if not coastal_edges:
            return

        if len(self.hexes) == 19 and len(coastal_edges) >= 9:
            port_count = 9
            assignments: list[tuple[int, ResourceType | None]] = [
                (2, ResourceType.TIMBER),
                (2, ResourceType.STONE),
                (2, ResourceType.MEAT),
                (2, ResourceType.GRAIN),
                (2, ResourceType.IRON),
                (3, None),
                (3, None),
                (3, None),
                (3, None),
            ]
        else:
            port_count = max(1, min(9, len(coastal_edges) // 3))
            assignments = [(3, None)] * port_count

        step = len(coastal_edges) / port_count
        chosen_indices = sorted({int(i * step) % len(coastal_edges) for i in range(port_count)})
        while len(chosen_indices) < port_count:
            candidate = len(chosen_indices) % len(coastal_edges)
            if candidate not in chosen_indices:
                chosen_indices.append(candidate)
        chosen_indices = sorted(chosen_indices[:port_count])

        rng.shuffle(assignments)
        for port_id, (edge_index, assignment) in enumerate(zip(chosen_indices, assignments)):
            edge = coastal_edges[edge_index]
            rate, resource = assignment
            self.ports[port_id] = Port(
                port_id=port_id,
                edge_id=edge.edge_id,
                vertex_ids=(edge.v1, edge.v2),
                rate=rate,
                resource=resource,
            )

    def configure_ports(self, custom_ports: list[dict[str, Any]]) -> None:
        self.ports.clear()
        coastal_edge_ids = {edge.edge_id for edge in self.edges.values() if len(edge.touching_hexes) == 1}
        used_edges: set[int] = set()

        for port_id, item in enumerate(custom_ports):
            edge_id = int(item["edge_id"])
            rate = int(item["rate"])
            resource_raw = item.get("resource")

            if edge_id not in self.edges:
                raise ValueError(f"Port edge {edge_id} is not a valid edge")
            if edge_id not in coastal_edge_ids:
                raise ValueError(f"Port edge {edge_id} is not coastal")
            if edge_id in used_edges:
                raise ValueError(f"Port edge {edge_id} already assigned")
            if rate not in (2, 3, 4):
                raise ValueError("Port rate must be 2, 3, or 4")

            resource: ResourceType | None
            if resource_raw is None:
                resource = None
            elif isinstance(resource_raw, ResourceType):
                resource = resource_raw
            else:
                try:
                    resource = ResourceType(resource_raw)
                except Exception as exc:
                    raise ValueError(f"Invalid port resource: {resource_raw}") from exc

            if resource == ResourceType.WASTELAND:
                raise ValueError("Port resource cannot be Wasteland")
            if rate == 2 and resource is None:
                raise ValueError("A 2:1 port must specify a resource")

            edge = self.edges[edge_id]
            self.ports[port_id] = Port(
                port_id=port_id,
                edge_id=edge_id,
                vertex_ids=(edge.v1, edge.v2),
                rate=rate,
                resource=resource,
            )
            used_edges.add(edge_id)

    def _build_resource_list(self, tile_count: int, rng: random.Random) -> list[ResourceType]:
        if tile_count == 19:
            resources = (
                [ResourceType.TIMBER] * 4
                + [ResourceType.STONE] * 3
                + [ResourceType.MEAT] * 4
                + [ResourceType.GRAIN] * 4
                + [ResourceType.IRON] * 3
                + [ResourceType.WASTELAND]
            )
        else:
            resources = [ResourceType.TIMBER, ResourceType.STONE, ResourceType.MEAT, ResourceType.GRAIN, ResourceType.IRON]
            resource_tiles = [resources[i % len(resources)] for i in range(tile_count - 1)] + [ResourceType.WASTELAND]
            resources = resource_tiles

        rng.shuffle(resources)
        return resources

    def _build_token_list(self, tile_count: int, rng: random.Random) -> list[int]:
        non_desert_tiles = tile_count - 1
        standard_tokens = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]

        if non_desert_tiles == len(standard_tokens):
            tokens = standard_tokens[:]
        else:
            cycle = [2, 3, 4, 5, 6, 8, 9, 10, 11, 12]
            tokens = [cycle[i % len(cycle)] for i in range(non_desert_tiles)]

        rng.shuffle(tokens)
        return tokens

    def can_place_settlement(self, vertex_id: int, player_id: int, require_connected_road: bool = False) -> bool:
        vertex = self.vertices[vertex_id]
        if vertex.occupied:
            return False

        for neighbor_id in vertex.adjacent_vertices:
            if self.vertices[neighbor_id].occupied:
                return False

        if not require_connected_road:
            return True

        for edge_id in vertex.adjacent_edges:
            edge = self.edges[edge_id]
            if edge.road_owner == player_id:
                return True

        return False

    def can_place_road(self, edge_id: int, player_id: int) -> bool:
        edge = self.edges[edge_id]
        if edge.occupied:
            return False

        v1 = self.vertices[edge.v1]
        v2 = self.vertices[edge.v2]

        if (v1.building_owner == player_id and v1.occupied) or (v2.building_owner == player_id and v2.occupied):
            return True

        for connected_edge_id in v1.adjacent_edges | v2.adjacent_edges:
            if connected_edge_id == edge_id:
                continue
            if self.edges[connected_edge_id].road_owner == player_id:
                return True

        return False

    def get_ports_for_vertex(self, vertex_id: int) -> list[Port]:
        return [port for port in self.ports.values() if vertex_id in port.vertex_ids]
