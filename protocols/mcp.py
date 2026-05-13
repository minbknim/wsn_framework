"""MCP/MCP+ 최종판 v2 — 예비링크·균등분배·적응형가중치"""
from __future__ import annotations
import math, random
from typing import Dict, List, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class MCP(BaseProtocol):
    name = "MCP"
    default_params = {
        "num_levels":    3,
        "w_dist":        0.6,
        "w_energy":      0.4,
        "enable_backup": True,
        "balance_chains":True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chain_ids: List[List[int]] = []
        self._backup_link: Dict[int, int] = {}
        self._rng = random.Random(42)

    def _rd(self, node, bs):
        d = node.distance_to_point(bs.x, bs.y)
        E = max(node.energy, 1e-9)
        return self.params["w_dist"]*d + self.params["w_energy"]*(1/E)

    def _greedy_chain(self, nodes):
        if not nodes: return []
        rem = list(nodes)
        start = max(rem, key=lambda n: n.distance_to_point(0,0))
        chain=[start]; rem.remove(start)
        while rem:
            nxt=min(rem,key=lambda n:chain[-1].distance_to(n))
            chain.append(nxt); rem.remove(nxt)
        return chain

    def _balance(self, chains):
        if not self.params["balance_chains"] or len(chains)<2: return chains
        for _ in range(5):
            ls=[len(c) for c in chains]
            if max(ls)-min(ls)<=1: break
            big=ls.index(max(ls)); sml=ls.index(min(ls))
            chains[sml].append(chains[big].pop())
        return chains

    def _build_backup(self, chains):
        if not self.params["enable_backup"]: return {}
        rns=[c[-1].node_id for c in chains if c]
        bk={}
        for i,rn in enumerate(rns):
            if i>0: bk[rn]=rns[i-1]
            if i<len(rns)-1: bk[rn]=rns[i+1]
        return bk

    def _build_multi_chains(self, alive, bs):
        if not alive: return []
        n=max(1,self.params["num_levels"])
        sn=sorted(alive,key=lambda nd:self._rd(nd,bs))
        sz=max(1,len(sn)//n)
        groups=[sn[i*sz:(i+1)*sz if i<n-1 else len(sn)] for i in range(n) if i*sz<len(sn)]
        chains=[self._greedy_chain(g) for g in groups if g]
        chains=self._balance(chains)
        self._backup_link=self._build_backup(chains)
        self._chain_ids=[[nd.node_id for nd in c] for c in chains]
        return self._chain_ids

    def select_cluster_heads(self, alive, rnd, bs):
        if not alive: return [],{}
        nm={n.node_id:n for n in alive}
        chains=self._build_multi_chains(alive,bs)
        ch_ids=[]; cm={}
        for chain in chains:
            valid=[nid for nid in chain if nid in nm]
            if not valid: continue
            rn=valid[-1]
            if rn not in nm:
                bk=self._backup_link.get(rn)
                rn=bk if bk and bk in nm else valid[0]
            ch_ids.append(rn)
            for nid in valid: cm[nid]=rn
        return ch_ids,cm

    def run_round(self, alive, ch_ids, cm, bs, rnd):
        if not ch_ids or not self._chain_ids: return 0
        nm={n.node_id:n for n in alive}
        pkt=self.comm.packet_size; pkts=0
        for chain in self._chain_ids:
            valid=[nid for nid in chain if nid in nm and nm[nid].alive]
            if not valid: continue
            rn_id=cm.get(valid[-1],valid[-1])
            rn=nm.get(rn_id)
            if not rn or not rn.alive:
                bk=self._backup_link.get(rn_id)
                if bk and bk in nm and nm[bk].alive: rn=nm[bk]
                else: continue
            for nid in valid[:-1]:
                nd=nm.get(nid)
                if nd and nd.alive: self._dissipate_member(nd,rn)
            members=[nm[nid] for nid in valid[:-1] if nid in nm and nm[nid].alive]
            if self._dissipate_ch(rn,members,bs,pkt): pkts+=1
        return pkts


class MCP_PLUS(MCP):
    name="MCP+"
    default_params={**MCP.default_params,"differential":True,"reset_k":150}

    def __init__(self,*a,**k):
        super().__init__(*a,**k)
        self._last_reset=0

    def run_round(self,alive,ch_ids,cm,bs,rnd):
        is_reset=(rnd-self._last_reset>=self.params["reset_k"])
        if is_reset: self._last_reset=rnd
        orig=self.comm.packet_size
        if self.params["differential"] and not is_reset:
            self.comm.packet_size=orig//2
        pkts=super().run_round(alive,ch_ids,cm,bs,rnd)
        self.comm.packet_size=orig
        return pkts
