from __future__ import annotations
import streamlit as st
from datetime import date
from db import (
    create_group, get_group_by_code, join_member, list_members,
    add_expense_equal, add_expense_custom, list_expenses, list_splits_for_group,
    delete_expense, to_paise, inr
)
from debt import settle_minimal

st.set_page_config(page_title="Splitwise Lite (INR)", page_icon="💸", layout="centered")

if "group" not in st.session_state:
    st.session_state.group = None
if "member" not in st.session_state:
    st.session_state.member = None

st.title("Splitwise-lite • INR")

code_param = st.query_params.get("code", "").upper().strip() if hasattr(st, "query_params") else ""

with st.sidebar:
    st.header("Group")
    if st.session_state.group:
        st.success(f'Code: {st.session_state.group["code"]}')
        st.caption(f'Name: {st.session_state.group["name"]}')
        st.caption("PIN: " + ("set" if st.session_state.group.get("pin") else "not set"))
    else:
        st.info("No group chosen")

# ---------- Landing: create or join ----------
if not code_param and not st.session_state.group:
    st.subheader("Create a new group")
    name = st.text_input("Trip name", placeholder="Goa Oct 2025")
    pin = st.text_input("Optional PIN (numbers or letters)", type="password", help="Leave empty for no PIN")
    if st.button("Create group"):
        if not name.strip():
            st.error("Enter a trip name")
        else:
            grp = create_group(name.strip(), pin.strip() or None)
            st.query_params["code"] = grp["code"]
            st.session_state.group = grp
            st.rerun()

    st.divider()
    st.subheader("Join existing group")
    join_code = st.text_input("Enter group code", placeholder="GOA25")
    if st.button("Join"):
        grp = get_group_by_code(join_code.strip())
        if not grp:
            st.error("Group not found")
        else:
            st.query_params["code"] = grp["code"]
            st.session_state.group = grp
            st.rerun()
else:
    if not st.session_state.group:
        grp = get_group_by_code(code_param)
        if grp:
            st.session_state.group = grp
        else:
            st.error("Invalid group code in URL")
            st.stop()

    group = st.session_state.group

    # If group has a PIN, ask it before joining as member
    if not st.session_state.member:
        st.subheader(f'Join “{group["name"]}”')
        needs_pin = bool(group.get("pin"))
        if needs_pin:
            pin_try = st.text_input("Group PIN", type="password")
        display_name = st.text_input("Your name", placeholder="Ravi")
        if st.button("Enter group"):
            if not display_name.strip():
                st.error("Enter your name")
            elif needs_pin and (pin_try.strip() != (group.get("pin") or "")):
                st.error("Wrong PIN")
            else:
                mem = join_member(group["id"], display_name.strip())
                st.session_state.member = mem
                st.success(f'Joined as {mem["display_name"]}')
                st.rerun()
        st.stop()

    member = st.session_state.member
    st.caption(f'You are: **{member["display_name"]}**')

    # Caches
    @st.cache_data(ttl=5)
    def _members(group_id: str):
        return list_members(group_id)

    @st.cache_data(ttl=5)
    def _expenses(group_id: str):
        return list_expenses(group_id)

    @st.cache_data(ttl=5)
    def _splits(group_id: str):
        return list_splits_for_group(group_id)

    tabs = st.tabs(["➕ Add expense", "📜 Expenses", "🧮 Balances", "✅ Settle", "👥 Members"])

    # ---------- Add expense ----------
    with tabs[0]:
        members = _members(group["id"])
        if not members:
            st.warning("No members yet")
        else:
            payer_names = {m["display_name"]: m["id"] for m in members}
            payer_name = st.selectbox("Who paid?", options=list(payer_names.keys()), index=0)
            desc = st.text_input("Description", placeholder="Dinner")
            amt_str = st.text_input("Amount (₹)", placeholder="900")
            exp_date = st.date_input("Date", value=date.today(), format="DD/MM/YYYY")
            chosen = st.multiselect(
                "Split with",
                options=[m["display_name"] for m in members],
                default=[m["display_name"] for m in members],
            )
            split_kind = st.radio("Split type", ["Equal", "Custom"], horizontal=True)

            custom_weights = []
            if split_kind == "Custom":
                st.caption("Give simple integer weights. Example: Alice 2, Bob 1 means 2/3 and 1/3.")
                for name in chosen:
                    w = st.number_input(f"Weight for {name}", min_value=0, value=1, step=1)
                    custom_weights.append(int(w))

            if st.button("Add"):
                if not desc.strip():
                    st.error("Enter description")
                else:
                    paise = to_paise(amt_str)
                    if paise <= 0:
                        st.error("Enter a positive amount")
                    elif not chosen:
                        st.error("Select at least one member")
                    else:
                        member_ids = [m["id"] for m in members if m["display_name"] in chosen]
                        if split_kind == "Equal":
                            add_expense_equal(
                                group_id=group["id"],
                                payer_id=payer_names[payer_name],
                                description=desc.strip(),
                                amount_paise=paise,
                                member_ids=member_ids,
                                expense_date=exp_date,
                            )
                        else:
                            # align weights with chosen members order
                            if len(custom_weights) != len(member_ids):
                                st.error("Set all weights")
                                st.stop()
                            add_expense_custom(
                                group_id=group["id"],
                                payer_id=payer_names[payer_name],
                                description=desc.strip(),
                                amount_paise=paise,
                                member_ids=member_ids,
                                weights=custom_weights,
                                expense_date=exp_date,
                            )
                        st.success("Added")
                        _expenses.clear(); _splits.clear()
                        st.rerun()

    # ---------- Expenses (with delete) ----------
    with tabs[1]:
        exps = _expenses(group["id"])
        mem_map = {m["id"]: m["display_name"] for m in _members(group["id"])}
        if not exps:
            st.info("No expenses yet")
        else:
            for e in exps:
                col1, col2 = st.columns([4,1])
                with col1:
                    st.write(
                        f'**{e["description"]}** — {inr(e["amount_paise"])} • '
                        f'Paid by {mem_map.get(e["payer_id"], "Unknown")} • '
                        f'Date {e["expense_date"]} • {e["split_type"]}'
                    )
                with col2:
                    if st.button("Delete", key=f"del-{e['id']}"):
                        delete_expense(e["id"])
                        st.warning("Deleted")
                        _expenses.clear(); _splits.clear()
                        st.rerun()

    # ---------- Balances ----------
    def compute_nets(group_id: str):
        exps = _expenses(group_id)
        splits = _splits(group_id)
        members = _members(group_id)
        paid = {m["id"]: 0 for m in members}
        owed = {m["id"]: 0 for m in members}
        for e in exps:
            paid[e["payer_id"]] += e["amount_paise"]
        for s in splits:
            owed[s["member_id"]] += s["share_paise"]
        nets = {m["id"]: paid[m["id"]] - owed[m["id"]] for m in members}
        names = {m["id"]: m["display_name"] for m in members}
        return nets, names

    with tabs[2]:
        nets, names = compute_nets(group["id"])
        if not names:
            st.info("No members")
        else:
            rows = []
            for mid, net in nets.items():
                status = "to receive" if net > 0 else ("to pay" if net < 0 else "settled")
                rows.append(f'{names[mid]}: {inr(abs(net))} {status}')
            st.write("\n\n".join(rows) if rows else "No data")

    # ---------- Settle ----------
    with tabs[3]:
        nets, names = compute_nets(group["id"])
        transfers = settle_minimal(nets)
        if not transfers:
            st.success("All settled")
        else:
            for frm, to, paise in transfers:
                st.write(f'{names[frm]} pays {names[to]} {inr(paise)}')

    # ---------- Members ----------
    with tabs[4]:
        ms = _members(group["id"])
        if not ms:
            st.info("No members")
        else:
            for m in ms:
                st.write(f'- {m["display_name"]}')
