"""Verification test for pricing, payments, history summary."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from seed import seed_database
from app.main import app
from fastapi.testclient import TestClient

seed_database()

with TestClient(app) as c:
    print("\n=== TEST 1: /estimate pricing (normal < fast < emergency) ===")
    results = {}
    for p in ["normal", "fast", "emergency"]:
        r = c.post("/estimate", json={"vehicle_id": 1, "current_percent": 20, "target_percent": 70, "priority": p})
        assert r.status_code == 200, f"estimate failed {p}: {r.text}"
        d = r.json()
        results[p] = d
        expected_tax = round((d["energy_cost"] + d["booking_fee"]) * 0.05, 2)
        assert abs(d["tax"] - expected_tax) < 0.01, f"Tax mismatch for {p}: got {d['tax']} expected {expected_tax}"
        print(f"  {p}: kWh={d['kwh']}, energy=Rs{d['energy_cost']}, fee=Rs{d['booking_fee']}, tax=Rs{d['tax']}, TOTAL=Rs{d['total']}")

    assert results["normal"]["total"] < results["fast"]["total"] < results["emergency"]["total"], "Totals not ascending!"
    print("[PASS] Totals ascending: normal < fast < emergency")
    print("[PASS] Tax formula verified for all priorities")

    print("\n=== TEST 2: Book+release with real kWh, verify ChargingHistory.cost ===")
    # Book vehicle 1 at station 1
    r = c.post("/book", json={"vehicle_id": 1, "station_id": 1, "priority": "fast"})
    assert r.status_code == 200, r.text
    bk = r.json()
    assert bk["result"] == "assigned", f"Expected assigned: {bk}"
    booking_id = bk["booking_id"]
    slot_id = bk["slot_id"]
    print(f"  Booked vehicle 1 -> booking #{booking_id}, slot #{slot_id}, priority=fast")

    # Release with exact kWh
    kwh_delivered = 20.0
    r = c.post(f"/release/{slot_id}", json={"energy_used": kwh_delivered, "rate_per_kwh": 15.0, "charger_power_kw": 50.0})
    assert r.status_code == 200, r.text
    rel = r.json()

    # The cost must match pricing.calculate_estimate(kwh=20, priority='fast', slot_type=...)
    from app import pricing
    slot_type = "fast" if "fast" in str(slot_id) else "normal"  # we know station 1 has mixed
    est = pricing.calculate_estimate(kwh=kwh_delivered, priority="fast", slot_type="fast")
    print(f"  Release cost: Rs{rel['cost']}, Expected from pricing: Rs{est['total']}")
    assert abs(rel["cost"] - est["total"]) < 0.01, f"Cost mismatch: got {rel['cost']} expected {est['total']}"
    print("[PASS] ChargingHistory cost matches pricing.calculate_estimate")

    print("\n=== TEST 3: POST /payments - wrong amount rejected, correct succeeds, double-pay rejected ===")
    # Wrong amount
    r = c.post("/payments", json={"booking_id": booking_id, "upi_id": "test@upi", "amount": 1.00})
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    print("  [PASS] Wrong amount rejected (400)")

    # Correct amount
    r = c.post("/payments", json={"booking_id": booking_id, "upi_id": "test@upi", "amount": rel["cost"]})
    assert r.status_code == 200, f"Payment failed: {r.text}"
    pay = r.json()
    assert pay["status"] == "paid"
    assert pay["upi_ref"].startswith("UPI")
    assert len(pay["upi_ref"]) == 15  # 'UPI' + 12 digits
    print(f"  [PASS] Payment accepted: ref={pay['upi_ref']}, amount=Rs{pay['amount']}")

    # Double payment rejected
    r = c.post("/payments", json={"booking_id": booking_id, "upi_id": "test@upi", "amount": rel["cost"]})
    assert r.status_code == 400, f"Expected 400 for double-pay, got {r.status_code}"
    print("  [PASS] Double payment rejected (400)")

    print("\n=== TEST 4: History summary across 3 sessions / 2 stations ===")
    # Complete 2 more sessions
    r2 = c.post("/book", json={"vehicle_id": 1, "station_id": 1, "priority": "normal"})
    assert r2.status_code == 200, r2.text
    bk2 = r2.json()
    assert bk2["result"] == "assigned", str(bk2)
    r3 = c.post(f"/release/{bk2['slot_id']}", json={"energy_used": 15.0, "rate_per_kwh": 12.0, "charger_power_kw": 22.0})
    assert r3.status_code == 200, r3.text
    cost2 = r3.json()["cost"]

    # Session at station 2
    r4 = c.post("/book", json={"vehicle_id": 1, "station_id": 2, "priority": "normal"})
    assert r4.status_code == 200, r4.text
    bk4 = r4.json()
    assert bk4["result"] == "assigned", str(bk4)
    r5 = c.post(f"/release/{bk4['slot_id']}", json={"energy_used": 10.0, "rate_per_kwh": 12.0, "charger_power_kw": 22.0})
    assert r5.status_code == 200, r5.text
    cost3 = r5.json()["cost"]

    summary = c.get("/history/vehicle/1/summary").json()
    print(f"  Sessions: {summary['total_sessions']}, TotalSpent: Rs{summary['total_spent']}")
    assert summary["total_sessions"] == 3, f"Expected 3 sessions, got {summary['total_sessions']}"
    
    expected_total = round(rel["cost"] + cost2 + cost3, 2)
    actual_total = summary["total_spent"]
    assert abs(actual_total - expected_total) < 0.05, f"Total spent mismatch: got {actual_total} expected {expected_total}"
    print(f"  [PASS] 3 sessions, total_spent Rs{actual_total} matches sum of costs")

    # Check by_station: station 1 should have 2 visits, station 2 should have 1
    station_visits = {s["station_id"]: s["visits"] for s in summary["by_station"]}
    assert station_visits.get(1, 0) == 2, f"Station 1 expected 2 visits, got {station_visits.get(1,0)}"
    assert station_visits.get(2, 0) == 1, f"Station 2 expected 1 visit, got {station_visits.get(2,0)}"
    print(f"  [PASS] by_station visits correct: station1={station_visits[1]}, station2={station_visits[2]}")

    print("\n=== ALL PRICING + PAYMENTS + HISTORY TESTS PASSED! ===")
