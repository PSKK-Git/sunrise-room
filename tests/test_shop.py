import json
import shutil
from pathlib import Path

import pytest

from shop import shopctl


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    dst = tmp_path / "data.json"
    shutil.copy(Path(shopctl.__file__).with_name("data.json"), dst)
    monkeypatch.setattr(shopctl, "DATA", dst)
    return dst


def test_status_shows_broken_machine_and_low_stock():
    out = shopctl.run(["status"])
    assert "machine 3" in out and "Low stock: detergent_5l" in out


def test_machine_lookup_links_affected_order():
    assert "affects order O5001" in shopctl.run(["machine", "3"])


def test_unknown_machine_is_an_error():
    with pytest.raises(shopctl.ShopError):
        shopctl.run(["machine", "99"])


def test_staging_a_refund_changes_nothing_until_approved(data):
    out = shopctl.run(["stage", "refund", "O5001", "180", "machine 3 fault", "--by", "Ravi"])
    assert out.startswith("P1 is waiting")
    db = json.loads(data.read_text())
    assert db["orders"][0]["status"] == "in_progress"


def test_only_the_owner_can_approve(data):
    shopctl.run(["stage", "refund", "O5001", "180", "fault", "--by", "Ravi"])
    with pytest.raises(shopctl.ShopError, match="only Owner"):
        shopctl.run(["approve", "P1", "--by", "Ravi"])
    assert json.loads(data.read_text())["pending"][0]["state"] == "waiting"


def test_owner_approval_applies_the_refund_and_logs(data):
    shopctl.run(["stage", "refund", "O5001", "180", "fault", "--by", "Ravi"])
    out = shopctl.run(["approve", "P1", "--by", "owner"])
    assert "approved" in out
    db = json.loads(data.read_text())
    assert db["orders"][0]["status"] == "refunded"
    assert db["log"][0]["by"] == "owner"


def test_cannot_decide_twice(data):
    shopctl.run(["stage", "repair", "3", "E21 fault", "--by", "Ravi"])
    shopctl.run(["approve", "P1", "--by", "Owner"])
    with pytest.raises(shopctl.ShopError, match="already approved"):
        shopctl.run(["reject", "P1", "--by", "Owner"])


def test_refund_cannot_exceed_order_total():
    with pytest.raises(shopctl.ShopError):
        shopctl.run(["stage", "refund", "O5001", "999", "oops", "--by", "Ravi"])
    with pytest.raises(shopctl.ShopError):
        shopctl.run(["stage", "refund", "O5001", "0", "oops", "--by", "Ravi"])


def test_reject_leaves_everything_unchanged(data):
    shopctl.run(["stage", "reorder", "detergent_5l", "6", "--by", "Meena"])
    shopctl.run(["reject", "P1", "not now", "--by", "Owner"])
    db = json.loads(data.read_text())
    assert db["stock"][0]["qty"] == 2
    assert db["pending"][0]["state"] == "rejected"


def test_reorder_applies_after_approval(data):
    shopctl.run(["stage", "reorder", "detergent_5l", "6", "--by", "Meena"])
    shopctl.run(["approve", "P1", "--by", "Owner"])
    assert json.loads(data.read_text())["stock"][0]["qty"] == 8


def test_refund_cannot_be_staged_twice_past_the_order_total(data):
    """Regression: two staged refunds on one order could together exceed what was paid."""
    shopctl.run(["stage", "refund", "O5001", "180", "fault", "--by", "Ravi"])
    with pytest.raises(shopctl.ShopError, match="left to refund"):
        shopctl.run(["stage", "refund", "O5001", "50", "again", "--by", "Meena"])
    shopctl.run(["approve", "P1", "--by", "Owner"])
    with pytest.raises(shopctl.ShopError, match="left to refund"):
        shopctl.run(["stage", "refund", "O5001", "1", "again", "--by", "Meena"])


def test_partial_refunds_accumulate(data):
    shopctl.run(["stage", "refund", "O5001", "100", "part", "--by", "Ravi"])
    shopctl.run(["approve", "P1", "--by", "Owner"])
    assert json.loads(data.read_text())["orders"][0]["status"] == "part_refunded"
    shopctl.run(["stage", "refund", "O5001", "80", "rest", "--by", "Ravi"])
    shopctl.run(["approve", "P2", "--by", "Owner"])
    assert json.loads(data.read_text())["orders"][0]["status"] == "refunded"


def test_pending_lists_only_waiting():
    assert "Nothing waiting" in shopctl.run(["pending"])
    shopctl.run(["stage", "repair", "3", "E21", "--by", "Ravi"])
    assert "P1" in shopctl.run(["pending"])
