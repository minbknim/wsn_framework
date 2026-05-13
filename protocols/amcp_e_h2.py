"""AMCP-E-H2 — 2-tier Hybrid: 클러스터(LEACH) + 내부체인(PEGASIS) + 차분전송"""
from __future__ import annotations
import random
from typing import Dict, List, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class AMCP_E_H2(BaseProtocol):
    name = "AMCP-E-H2"
    default_params = {
        "ch_ratio":    0.05,
        "reset_k":     500,
        "diff":        True,
        "e_min_ratio": 0.05,
    }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._rng = random.Random(42)
        self._not_ch_since: Dict[int,int] = {}
        self._last_reset = 0
        self._last_sent: Dict[int,bytes] = {}

    def _greedy_intra(self, members, ch):
        if not members: return []
        rem=list(members); chain=[]; cur=ch
        while rem:
            nxt=min(rem,key=lambda n:cur.distance_to(n))
            chain.append(nxt); rem.remove(nxt); cur=nxt
        return chain

    def select_cluster_heads(self, alive, rnd, bs):
        if not alive: return [],{}
        p=self.params["ch_ratio"]; T=int(1/p)
        emin=self.params["e_min_ratio"]
        ch_ids=[]
        for node in alive:
            if node.energy/max(node.initial_energy,1e-9)<emin: continue
            last=self._not_ch_since.get(node.node_id,0)
            if rnd-last>=T:
                mod=rnd%T or 1
                thr=min(p/(1-p*mod),1.0)
            else: thr=0.0
            if self._rng.random()<thr:
                ch_ids.append(node.node_id)
                self._not_ch_since[node.node_id]=rnd
        return ch_ids, self._assign_members_to_nearest_ch(alive,ch_ids)

    def run_round(self, alive, ch_ids, cm, bs, rnd):
        if not ch_ids or not cm: return 0
        K=self.params["reset_k"]
        is_reset=(rnd-self._last_reset>=K)
        if is_reset: self._last_reset=rnd; self._last_sent.clear()
        pkt=self.comm.packet_size if (is_reset or not self.params["diff"])             else self.comm.packet_size//2
        nm={n.node_id:n for n in alive}
        ch_members: Dict[int,List[SensorNode]]={c:[] for c in ch_ids}
        for node in alive:
            cid=cm.get(node.node_id)
            if cid and cid!=node.node_id and cid in nm:
                ch_members[cid].append(node)
        pkts=0
        for cid,members in ch_members.items():
            ch=nm.get(cid)
            if not ch or not ch.alive: continue
            if members:
                for m in sorted(members,key=lambda n:n.distance_to(ch)):
                    if m.alive: self._dissipate_member(m,ch)
            if not self._consume(ch, self.em.agg_energy(pkt*(len(members)+1))): continue
            if self._consume(ch, self.em.tx_energy(pkt, ch.distance_to_point(bs.x,bs.y))):
                pkts+=1
        return pkts
