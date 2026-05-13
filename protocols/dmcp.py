"""
Distributed Greedy MCP (분산형 그리디 체인)

개선방안 카테고리2 — 체인 구성 미구현 항목 완성
인접 노드 간 RD 정보 교환으로 로컬 레벨 결정
BS 중앙집중 없이 자율적 체인 구성 가능
"""
from __future__ import annotations
import random
from typing import Dict, List, Tuple
from .mcp import MCP
from wsn_framework.core.topology import SensorNode, BaseStation


class DMCP(MCP):
    """분산형 그리디 MCP — 인접 노드 RD 교환 기반."""
    name = "DMCP"
    default_params = {
        **MCP.default_params,
        "comm_range":     50.0,   # 이웃 통신 범위 (m)
        "n_iter":         3,      # 레벨 합의 반복 횟수
    }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._node_levels: Dict[int, int] = {}   # nid → level

    def _get_neighbors(self, node: SensorNode,
                        alive: List[SensorNode]) -> List[SensorNode]:
        r = self.params["comm_range"]
        return [n for n in alive
                if n.node_id != node.node_id
                and node.distance_to(n) <= r]

    def _distributed_leveling(self, alive: List[SensorNode],
                               bs: BaseStation) -> Dict[int, int]:
        """
        분산 레벨 결정:
        1. 각 노드가 자신의 RD 계산
        2. 이웃 노드와 RD 비교 → 상대적 레벨 결정
        3. n_iter 반복으로 수렴
        """
        n_lvl = max(1, self.params["num_levels"])
        # 초기 RD 계산
        rds = {n.node_id: self._rd(n, bs) for n in alive}
        rd_min = min(rds.values()); rd_max = max(rds.values())
        rd_range = max(rd_max - rd_min, 1e-9)

        # 정규화 RD → 레벨
        levels: Dict[int, int] = {}
        for n in alive:
            normalized = (rds[n.node_id] - rd_min) / rd_range
            levels[n.node_id] = min(n_lvl - 1,
                                    int(normalized * n_lvl))

        # 이웃과 n_iter 반복 합의 (로컬 평균)
        for _ in range(self.params["n_iter"]):
            new_levels = dict(levels)
            for node in alive:
                nbrs = self._get_neighbors(node, alive)
                if nbrs:
                    # 이웃 레벨 평균으로 조정
                    avg = (levels[node.node_id] +
                           sum(levels[nb.node_id] for nb in nbrs)) / (len(nbrs) + 1)
                    new_levels[node.node_id] = min(n_lvl - 1, int(avg))
            levels = new_levels

        return levels

    def _build_multi_chains(self, alive: List[SensorNode],
                             bs: BaseStation) -> List[List[int]]:
        """분산 레벨링 기반 체인 구성."""
        if not alive: return []
        levels = self._distributed_leveling(alive, bs)
        n_lvl  = max(1, self.params["num_levels"])

        # 레벨별 그룹
        groups: Dict[int, List[SensorNode]] = {i: [] for i in range(n_lvl)}
        for node in alive:
            lv = levels.get(node.node_id, 0)
            groups[lv].append(node)

        chains_nodes = [self._greedy_chain(g)
                        for g in groups.values() if g]
        chains_nodes  = self._balance(chains_nodes)
        self._backup_link = self._build_backup(chains_nodes)
        self._chain_ids   = [[n.node_id for n in c] for c in chains_nodes]
        return self._chain_ids
