"""shopctl: the shop's back office, as a command line the room's agents can run.

Reading is free. Anything that spends money or changes a customer's order is
STAGED and only runs when the owner approves it:

    python -m shop.shopctl status
    python -m shop.shopctl machine 3
    python -m shop.shopctl stock
    python -m shop.shopctl order O5001
    python -m shop.shopctl stage refund O5001 180 "machine 3 fault, clothes still wet" --by Ravi
    python -m shop.shopctl stage repair 3 "E21 fault" --by Ravi
    python -m shop.shopctl stage reorder detergent_5l 6 --by Meena
    python -m shop.shopctl pending
    python -m shop.shopctl approve P1 --by Owner
    python -m shop.shopctl reject P1 "not needed" --by Owner

The data file defaults to shop/data.json; set SHOP_DATA to use a copy
(the demo resets from data.json, see scripts/reset_demo.sh).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

DATA = Path(os.environ.get("SHOP_DATA", Path(__file__).with_name("data.json")))

# Small refunds are not worth the owner's time; anything above needs approval.
AUTO_REFUND_LIMIT = 0  # stricter default for the demo: every refund goes to the owner


class ShopError(Exception):
    pass


def load() -> dict:
    return json.loads(DATA.read_text())


def save(db: dict) -> None:
    DATA.write_text(json.dumps(db, indent=2))


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _find(items, key, value, label):
    for it in items:
        if str(it[key]).lower() == str(value).lower():
            return it
    raise ShopError(f"no {label} '{value}'")


# ---------------------------------------------------------------- read side
def status(db: dict) -> str:
    lines = [f"{db['shop']}"]
    broken = [m for m in db["machines"] if m["status"] != "ok"]
    lines.append(f"Machines: {len(db['machines']) - len(broken)} ok, {len(broken)} need attention")
    for m in broken:
        lines.append(f"  machine {m['id']} ({m['kind']}): {m['status']} - {m['notes']}")
    low = [s for s in db["stock"] if s["qty"] <= s["reorder_at"]]
    for s in low:
        lines.append(f"Low stock: {s['item']} has {s['qty']} (reorder at {s['reorder_at']}, {s['supplier']} delivers {s['delivery_day']})")
    open_orders = [o for o in db["orders"] if o["status"] != "done"]
    lines.append(f"Open orders: {len(open_orders)}")
    lines.append(f"Waiting for the owner: {len(db['pending'])}")
    return "\n".join(lines)


def machine(db: dict, mid) -> str:
    m = _find(db["machines"], "id", mid, "machine")
    out = f"machine {m['id']}: {m['kind']}, {m['capacity_kg']}kg, status {m['status']}"
    if m["notes"]:
        out += f" - {m['notes']}"
    affected = [o for o in db["orders"] if o["machine"] == m["id"] and o["status"] != "done"]
    for o in affected:
        out += f"\n  affects order {o['id']} ({o['items']})"
    return out


def stock(db: dict) -> str:
    return "\n".join(
        f"{s['item']}: {s['qty']} (reorder at {s['reorder_at']}) - {s['supplier']}, delivers {s['delivery_day']}, Rs {s['unit_price']} each"
        for s in db["stock"]
    )


def order(db: dict, oid) -> str:
    o = _find(db["orders"], "id", oid, "order")
    c = _find(db["customers"], "id", o["customer"], "customer")
    return (
        f"order {o['id']}: {c['name']} (phone ends {c['phone_last4']}, {c['orders']} past orders)\n"
        f"  {o['items']} on machine {o['machine']}, Rs {o['amount']}, status {o['status']}"
    )


def pending(db: dict) -> str:
    waiting = [p for p in db["pending"] if p["state"] == "waiting"]
    if not waiting:
        return "Nothing waiting for the owner."
    return "\n".join(f"{p['id']}: {p['summary']} (asked by {p['by']} at {p['at']})" for p in waiting)


# --------------------------------------------------------------- write side
def _new_id(db: dict) -> str:
    return f"P{len(db['pending']) + 1}"


def stage(db: dict, kind: str, args: list[str], by: str) -> str:
    if kind == "refund":
        if len(args) < 3:
            raise ShopError("usage: stage refund <order> <amount> <reason>")
        o = _find(db["orders"], "id", args[0], "order")
        try:
            amount = int(args[1])
        except ValueError:
            raise ShopError("refund amount must be a whole number of rupees")
        if amount <= 0 or amount > o["amount"]:
            raise ShopError(f"refund must be between 1 and {o['amount']} (the order total)")
        # never let staged + already-refunded money exceed the order total (double refunds)
        committed = o.get("refunded", 0) + sum(
            p["action"]["amount"]
            for p in db["pending"]
            if p["state"] == "waiting" and p["action"]["type"] == "refund" and p["action"]["order"] == o["id"]
        )
        if committed + amount > o["amount"]:
            raise ShopError(f"order {o['id']} already has Rs {committed} refunded or waiting; only Rs {o['amount'] - committed} left to refund")
        summary = f"refund Rs {amount} on order {o['id']}: {args[2]}"
        action = {"type": "refund", "order": o["id"], "amount": amount}
    elif kind == "repair":
        if len(args) < 2:
            raise ShopError("usage: stage repair <machine> <problem>")
        m = _find(db["machines"], "id", args[0], "machine")
        summary = f"call technician for machine {m['id']}: {args[1]}"
        action = {"type": "repair", "machine": m["id"], "problem": args[1]}
    elif kind == "reorder":
        if len(args) < 2:
            raise ShopError("usage: stage reorder <item> <qty>")
        s = _find(db["stock"], "item", args[0], "stock item")
        try:
            qty = int(args[1])
        except ValueError:
            raise ShopError("quantity must be a whole number")
        if qty <= 0:
            raise ShopError("quantity must be positive")
        summary = f"reorder {qty} x {s['item']} from {s['supplier']} (Rs {qty * s['unit_price']})"
        action = {"type": "reorder", "item": s["item"], "qty": qty}
    else:
        raise ShopError("can stage: refund, repair, reorder")
    p = {"id": _new_id(db), "summary": summary, "action": action, "by": by, "at": _now(), "state": "waiting"}
    db["pending"].append(p)
    return f"{p['id']} is waiting for the owner: {summary}"


def _apply(db: dict, action: dict) -> str:
    t = action["type"]
    if t == "refund":
        o = _find(db["orders"], "id", action["order"], "order")
        o["refunded"] = o.get("refunded", 0) + action["amount"]
        o["status"] = "refunded" if o["refunded"] >= o["amount"] else "part_refunded"
        return f"refunded Rs {action['amount']} on {o['id']}"
    if t == "repair":
        m = _find(db["machines"], "id", action["machine"], "machine")
        m["status"] = "repair_booked"
        return f"technician booked for machine {m['id']}"
    if t == "reorder":
        s = _find(db["stock"], "item", action["item"], "stock item")
        s["qty"] += action["qty"]  # demo: delivery assumed; real life would add on arrival
        return f"ordered {action['qty']} x {s['item']}"
    raise ShopError(f"unknown action {t}")


def decide(db: dict, pid: str, approve: bool, by: str, why: str = "") -> str:
    owner = db["owner"]
    if by.lower() != owner.lower():
        raise ShopError(f"only {owner} can {'approve' if approve else 'reject'} this, not {by}")
    p = _find(db["pending"], "id", pid, "pending request")
    if p["state"] != "waiting":
        raise ShopError(f"{pid} was already {p['state']}")
    if approve:
        result = _apply(db, p["action"])
        p["state"] = "approved"
    else:
        result = f"rejected{': ' + why if why else ''}"
        p["state"] = "rejected"
    p["decided_by"], p["decided_at"] = by, _now()
    db["log"].append({"at": p["decided_at"], "pending": pid, "state": p["state"], "by": by, "result": result})
    return f"{pid} {p['state']} by {by}: {result}"


# --------------------------------------------------------------------- main
def run(argv: list[str]) -> str:
    ap = argparse.ArgumentParser(prog="shopctl")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("stock")
    sub.add_parser("pending")
    for name in ("machine", "order"):
        sub.add_parser(name).add_argument("id")
    st = sub.add_parser("stage")
    st.add_argument("kind")
    st.add_argument("args", nargs="+")
    st.add_argument("--by", required=True)
    ap_ = sub.add_parser("approve")
    ap_.add_argument("id")
    ap_.add_argument("--by", required=True)
    rj = sub.add_parser("reject")
    rj.add_argument("id")
    rj.add_argument("why", nargs="?", default="")
    rj.add_argument("--by", required=True)
    a = ap.parse_args(argv)

    db = load()
    if a.cmd == "status":
        return status(db)
    if a.cmd == "stock":
        return stock(db)
    if a.cmd == "pending":
        return pending(db)
    if a.cmd == "machine":
        return machine(db, a.id)
    if a.cmd == "order":
        return order(db, a.id)
    if a.cmd == "stage":
        out = stage(db, a.kind, a.args, a.by)
    elif a.cmd == "approve":
        out = decide(db, a.id, True, a.by)
    else:
        out = decide(db, a.id, False, a.by, a.why)
    save(db)
    return out


def main() -> None:
    try:
        print(run(sys.argv[1:]))
    except ShopError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
