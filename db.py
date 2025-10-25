from __future__ import annotations
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
import streamlit as st
import random, string
from datetime import date

@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

def new_code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))

# -------- Groups --------
def create_group(name: str, pin: Optional[str]) -> Dict[str, Any]:
    c = get_client()
    code = new_code()
    while c.table("groups").select("id").eq("code", code).execute().data:
        code = new_code()
    data = {"code": code, "name": name, "pin": pin if pin else None}
    res = c.table("groups").insert(data).execute()
    return res.data[0]

def get_group_by_code(code: str) -> Optional[Dict[str, Any]]:
    c = get_client()
    res = c.table("groups").select("*").eq("code", code.upper()).limit(1).execute()
    return res.data[0] if res.data else None

# -------- Members --------
def join_member(group_id: str, display_name: str) -> Dict[str, Any]:
    c = get_client()
    res = c.table("members").insert({"group_id": group_id, "display_name": display_name}).execute()
    return res.data[0]

def list_members(group_id: str) -> List[Dict[str, Any]]:
    c = get_client()
    return c.table("members").select("id,display_name,created_at").eq("group_id", group_id).order("created_at").execute().data

# -------- Expenses --------
def add_expense_equal(group_id: str, payer_id: str, description: str, amount_paise: int,
                      member_ids: List[str], expense_date: date) -> Dict[str, Any]:
    c = get_client()
    exp = c.table("expenses").insert({
        "group_id": group_id,
        "payer_id": payer_id,
        "description": description,
        "amount_paise": amount_paise,
        "split_type": "equal",
        "expense_date": str(expense_date),
    }).execute().data[0]

    n = len(member_ids)
    base = amount_paise // n
    remainder = amount_paise - base * n
    splits = []
    for i, mid in enumerate(member_ids):
        share = base + (1 if i < remainder else 0)
        splits.append({"expense_id": exp["id"], "member_id": mid, "share_paise": share})
    c.table("expense_splits").insert(splits).execute()
    return exp

def add_expense_custom(group_id: str, payer_id: str, description: str, amount_paise: int,
                       member_ids: List[str], weights: List[int], expense_date: date) -> Dict[str, Any]:
    c = get_client()
    exp = c.table("expenses").insert({
        "group_id": group_id,
        "payer_id": payer_id,
        "description": description,
        "amount_paise": amount_paise,
        "split_type": "custom",
        "expense_date": str(expense_date),
    }).execute().data[0]

    total_w = sum(max(0, int(w)) for w in weights)
    if total_w <= 0:
        return add_expense_equal(group_id, payer_id, description, amount_paise, member_ids, expense_date)

    raw = [amount_paise * int(w) / total_w for w in weights]
    floor_shares = [int(v) for v in raw]
    remainder = amount_paise - sum(floor_shares)
    frac_order = sorted(range(len(raw)), key=lambda i: raw[i] - floor_shares[i], reverse=True)
    for i in range(remainder):
        floor_shares[frac_order[i]] += 1

    splits = [{"expense_id": exp["id"], "member_id": mid, "share_paise": share}
              for mid, share in zip(member_ids, floor_shares)]
    c.table("expense_splits").insert(splits).execute()
    return exp

def list_expenses(group_id: str) -> List[Dict[str, Any]]:
    c = get_client()
    return (
        c.table("expenses")
        .select("id,description,amount_paise,created_at,payer_id,expense_date,split_type")
        .eq("group_id", group_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )

def list_splits_for_group(group_id: str) -> List[Dict[str, Any]]:
    c = get_client()
    exps = c.table("expenses").select("id").eq("group_id", group_id).execute().data
    if not exps:
        return []
    exp_ids = [e["id"] for e in exps]
    return c.table("expense_splits").select("expense_id,member_id,share_paise").in_("expense_id", exp_ids).execute().data

def delete_expense(expense_id: str) -> None:
    c = get_client()
    c.table("expenses").delete().eq("id", expense_id).execute()

# -------- Money helpers --------
def to_paise(amount_str: str) -> int:
    try:
        return int(round(float(amount_str) * 100))
    except:
        return 0

def inr(paise: int) -> str:
    return f"₹{paise/100:.2f}"
