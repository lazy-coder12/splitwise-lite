from __future__ import annotations
from typing import Dict, List, Tuple
import heapq

def settle_minimal(nets: Dict[str, int]) -> List[Tuple[str, str, int]]:
    creditors = [(-amt, mid) for mid, amt in nets.items() if amt > 0]
    debtors = [(amt, mid) for mid, amt in nets.items() if amt < 0]
    heapq.heapify(creditors)
    heapq.heapify(debtors)
    res = []
    while creditors and debtors:
        c_amt, c_id = heapq.heappop(creditors)
        d_amt, d_id = heapq.heappop(debtors)
        pay = min(-c_amt, -d_amt)
        res.append((d_id, c_id, pay))
        c_left = -c_amt - pay
        d_left = -d_amt - pay
        if c_left:
            heapq.heappush(creditors, (-c_left, c_id))
        if d_left:
            heapq.heappush(debtors, (-d_left, d_id))
    return res
