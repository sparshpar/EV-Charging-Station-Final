"""Test script for Tier 1, 2, and 3 backend endpoints."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from seed import seed_database
from app.main import app
from app.database import SessionLocal
from app.models import Vehicle
from fastapi.testclient import TestClient

def test_backend():
    print("=== 1. Wiping and reseeding database ===")
    seed_database()

    with TestClient(app) as client:
        print("\n=== 2. Testing Stations & Detail ===")
        r = client.get("/stations")
        assert r.status_code == 200
        stations = r.json()
        assert len(stations) == 15
        st1 = stations[0]
        assert "price_per_kwh" in st1
        assert st1["price_per_kwh"] == 18.0
        print(f"[PASS] GET /stations returned 15 stations with price_per_kwh = {st1['price_per_kwh']}")

        st1_id = st1["station_id"]
        r_det = client.get(f"/stations/{st1_id}")
        assert r_det.status_code == 200
        det = r_det.json()
        assert det["num_slots"] == 5
        assert det["free_slots"] == 5
        assert det["queue_length"] == 0
        assert "fast_slots_total" in det
        assert "normal_slots_total" in det
        print(f"[PASS] GET /stations/{st1_id} detail: {det['fast_slots_total']} fast, {det['normal_slots_total']} normal, queue: {det['queue_length']}")

        print("\n=== 3. Testing Booking to Full & Priority Promotion on Cancel ===")
        # Get demo vehicles
        r_users = client.get("/users")
        users = r_users.json()
        v1_id = users[0]["vehicle"]["vehicle_id"]
        v2_id = users[1]["vehicle"]["vehicle_id"]
        v3_id = users[2]["vehicle"]["vehicle_id"]
        v4_id = users[3]["vehicle"]["vehicle_id"]

        # Book slot 1
        b1 = client.post("/book", json={"vehicle_id": v1_id, "station_id": st1_id, "priority": "normal"}).json()
        assert b1["result"] == "assigned"
        booking1_id = b1["booking_id"]
        slot1_id = b1["slot_id"]

        # Fill remaining 4 slots with fleet EVs
        db = SessionLocal()
        extra_vs = []
        try:
            for i in range(10, 14):
                veh = Vehicle(user_id=users[0]["user_id"], model=f"Fleet EV {i}", plate_number=f"MH01FL00{i}", battery_capacity=50.0)
                db.add(veh)
                db.commit()
                db.refresh(veh)
                extra_vs.append(veh)
            for v in extra_vs:
                res = client.post("/book", json={"vehicle_id": v.vehicle_id, "station_id": st1_id, "priority": "normal"}).json()
                assert res["result"] == "assigned"
        finally:
            db.close()

        # Station is now full. Queue vehicle 2 (normal)
        q2 = client.post("/book", json={"vehicle_id": v2_id, "station_id": st1_id, "priority": "normal"}).json()
        assert q2["result"] == "queued"
        assert q2["position"] == 1

        # Queue vehicle 3 (emergency)
        q3 = client.post("/book", json={"vehicle_id": v3_id, "station_id": st1_id, "priority": "emergency"}).json()
        assert q3["result"] == "queued"
        # Emergency jumps ahead to position 1!
        assert q3["position"] == 1
        print("[PASS] Emergency vehicle queued at position 1 ahead of normal vehicle")

        # Check queue length in station detail
        r_det_q = client.get(f"/stations/{st1_id}").json()
        assert r_det_q["queue_length"] == 2
        print(f"[PASS] Station detail reports live queue_length = {r_det_q['queue_length']}")

        # Cancel active booking 1
        r_cancel = client.post(f"/cancel/{booking1_id}")
        assert r_cancel.status_code == 200
        c_data = r_cancel.json()
        assert c_data["promoted"] is not None
        assert c_data["promoted"]["vehicle_id"] == v3_id
        print(f"[PASS] POST /cancel/{booking1_id} promoted EMERGENCY vehicle {v3_id} first!")

        # Verify active booking endpoint for vehicle 3
        r_act = client.get(f"/bookings/vehicle/{v3_id}/active")
        assert r_act.status_code == 200
        act_data = r_act.json()
        assert act_data["vehicle_id"] == v3_id
        assert act_data["station_id"] == st1_id
        print(f"[PASS] GET /bookings/vehicle/{v3_id}/active returns active session at {act_data['station_name']}")

        print("\n=== 4. Testing POST /queue/leave/{vehicle_id} ===")
        # Queue vehicle 4 (normal)
        q4 = client.post("/book", json={"vehicle_id": v4_id, "station_id": st1_id, "priority": "normal"}).json()
        assert q4["result"] == "queued"
        # Vehicle 2 is at pos 1, Vehicle 4 is at pos 2
        pos2 = client.get(f"/queue/position/{v2_id}").json()["position"]
        pos4 = client.get(f"/queue/position/{v4_id}").json()["position"]
        assert pos2 == 1
        assert pos4 == 2

        # Leave queue for vehicle 2
        r_leave = client.post(f"/queue/leave/{v2_id}")
        assert r_leave.status_code == 200
        assert r_leave.json()["success"] is True

        # Now vehicle 2 should return 404 on position endpoint
        r_p2 = client.get(f"/queue/position/{v2_id}")
        assert r_p2.status_code == 404

        # Vehicle 4 should now be at position 1
        pos4_new = client.get(f"/queue/position/{v4_id}").json()["position"]
        assert pos4_new == 1
        print("[PASS] POST /queue/leave removed vehicle and re-indexed heap queue correctly")

        print("\n=== 5. Testing Release & Vehicle History (Multi-Table JOIN) ===")
        # Release slot 1 (currently occupied by vehicle 3)
        # Using computed kWh = 24.0, rate = 18.0
        r_rel = client.post(f"/release/{slot1_id}", json={"energy_used": 24.0, "rate_per_kwh": 18.0, "charger_power_kw": 50.0})
        assert r_rel.status_code == 200

        # Check vehicle history for vehicle 3
        r_vhist = client.get(f"/history/vehicle/{v3_id}")
        assert r_vhist.status_code == 200
        vhist = r_vhist.json()
        assert len(vhist) >= 1
        h0 = vhist[0]
        assert h0["station_name"] == "Mumbai Central EV Hub"
        assert h0["energy_used"] == 24.0
        from app.pricing import calculate_estimate
        exp = calculate_estimate(kwh=24.0, priority="emergency")
        assert abs(h0["cost"] - exp["total"]) < 0.05
        assert h0["payment_status"] == "pending"
        print(f"[PASS] GET /history/vehicle/{v3_id} returned multi-table JOIN: {h0['station_name']}, {h0['energy_used']} kWh, cost: Rs {h0['cost']}, status: {h0['payment_status']}")

        print("\n=== 6. Testing Reviews ===")
        r_rev = client.post("/reviews", json={
            "station_id": st1_id,
            "vehicle_id": v1_id,
            "rating": 5,
            "comment": "Super smooth automated queue and fast charging!"
        })
        assert r_rev.status_code == 200
        rev_data = r_rev.json()
        assert rev_data["rating"] == 5

        r_revs = client.get(f"/reviews/{st1_id}")
        assert r_revs.status_code == 200
        rev_list = r_revs.json()
        assert len(rev_list) >= 1
        print(f"[PASS] Reviews working: {len(rev_list)} reviews for station {st1_id}")

    print("\n=== ALL TIER 1, 2, 3 BACKEND TESTS PASSED! ===")

if __name__ == "__main__":
    test_backend()
