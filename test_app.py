"""Comprehensive test script verifying the capstone requirements."""

import sys
import os
import json
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from seed import seed_database
from app.main import app
from app.database import SessionLocal
from app.models import Station, Slot, User, Vehicle, Booking

TOWN_COORDS_KEYS = {
    "Mumbai", "Panvel", "Khopoli", "Khandala", "Lonavala", "Pune",
    "Bhiwandi", "Palghar", "Vapi", "Valsad", "Surat",
    "Mahad", "Chiplun", "Ratnagiri", "Goa"
}


def run_tests():
    print("=== STEP 1: Seeding database ===")
    seed_database()

    print("\n=== STEP 2: Running FastAPI TestClient Suite ===")
    # Using 'with TestClient(app) as client' triggers lifespan and hydrates slots
    with TestClient(app) as client:
        # Check Root
        r_root = client.get("/")
        assert r_root.status_code == 200, f"Expected 200 on /, got {r_root.status_code}"
        assert r_root.json() == {"message": "EV Charging Station Manager API is running"}
        print("[PASS] GET / responded 200 with API running message")

        # Check GET /stations
        r_stations = client.get("/stations")
        assert r_stations.status_code == 200
        stations = r_stations.json()
        assert len(stations) == 15, f"Expected 15 stations, got {len(stations)}"
        print(f"[PASS] GET /stations returned {len(stations)} stations")

        # Check Station Locations match Town Keys
        for st in stations:
            loc = st["location"]
            assert loc in TOWN_COORDS_KEYS, f"Location '{loc}' not in frontend coordinate map!"
        print("[PASS] All 15 station locations match the frontend coordinate keys")

        # Check Users & Vehicles
        r_users = client.get("/users")
        assert r_users.status_code == 200
        users = r_users.json()
        assert len(users) == 4, f"Expected 4 users, got {len(users)}"
        print(f"[PASS] GET /users returned {len(users)} demo profiles")

        # Pick Station 1 (Mumbai, 5 slots)
        st_id = stations[0]["station_id"]
        v1_id = users[0]["vehicle"]["vehicle_id"]
        v2_id = users[1]["vehicle"]["vehicle_id"]
        v3_id = users[2]["vehicle"]["vehicle_id"]
        v4_id = users[3]["vehicle"]["vehicle_id"]

        # First booking: vehicle 1 books station 1 with normal priority
        r_book1 = client.post("/book", json={"vehicle_id": v1_id, "station_id": st_id, "priority": "normal"})
        assert r_book1.status_code == 200
        data1 = r_book1.json()
        assert data1["result"] == "assigned", f"Expected assigned, got {data1}"
        slot1_id = data1["slot_id"]
        print(f"[PASS] POST /book assigned vehicle {v1_id} to slot {slot1_id} (Booking #{data1['booking_id']})")

        # Fill remaining 4 slots of station 1 with temporary test vehicles to test queue logic
        db = SessionLocal()
        extra_vehicles = []
        try:
            for i in range(5, 9):
                v_extra = Vehicle(user_id=users[0]["user_id"], model=f"Fleet EV {i}", plate_number=f"MH01ZZ{i}000", battery_capacity=50.0)
                db.add(v_extra)
                db.commit()
                db.refresh(v_extra)
                extra_vehicles.append(v_extra)

            for v in extra_vehicles:
                r_fill = client.post("/book", json={"vehicle_id": v.vehicle_id, "station_id": st_id, "priority": "normal"})
                assert r_fill.status_code == 200
                assert r_fill.json()["result"] == "assigned"
            print("[PASS] Successfully filled all 5 slots at Station 1")
        finally:
            db.close()

        # Now Station 1 is full.
        # Enqueue vehicle 2 with "normal" priority
        r_queue_norm = client.post("/book", json={"vehicle_id": v2_id, "station_id": st_id, "priority": "normal"})
        assert r_queue_norm.status_code == 200
        q_norm_data = r_queue_norm.json()
        assert q_norm_data["result"] == "queued"
        assert q_norm_data["position"] == 1
        print(f"[PASS] Vehicle {v2_id} (normal) queued at position {q_norm_data['position']}")

        # Enqueue vehicle 3 with "emergency" priority (even though arriving later!)
        r_queue_emerg = client.post("/book", json={"vehicle_id": v3_id, "station_id": st_id, "priority": "emergency"})
        assert r_queue_emerg.status_code == 200
        q_emerg_data = r_queue_emerg.json()
        assert q_emerg_data["result"] == "queued"
        # Since emergency has priority 0 vs normal priority 2, emergency MUST jump to position 1 in priority queue!
        assert q_emerg_data["position"] == 1, f"Expected emergency vehicle at position 1, got {q_emerg_data['position']}"
        print(f"[PASS] Priority Queue working! Vehicle {v3_id} (emergency) jumped ahead of vehicle {v2_id} to position 1")

        # Now release slot 1.
        # The emergency vehicle (v3_id) MUST be promoted immediately!
        r_rel = client.post(f"/release/{slot1_id}", json={"energy_used": 25.0, "rate_per_kwh": 15.0, "charger_power_kw": 50.0})
        assert r_rel.status_code == 200
        rel_data = r_rel.json()
        # Cost now flows through pricing.calculate_estimate (normal priority, includes tax+fee)
        # normal: energy_cost=25*12=300, fee=0, tax=15, total=315
        from app.pricing import calculate_estimate
        expected = calculate_estimate(kwh=25.0, priority="normal", slot_type="normal")
        assert abs(rel_data["cost"] - expected["total"]) < 0.01, f"Cost mismatch: got {rel_data['cost']} expected {expected['total']}"
        assert rel_data["promoted"] is not None, "Expected vehicle to be promoted from queue!"
        assert rel_data["promoted"]["vehicle_id"] == v3_id, f"Expected emergency vehicle {v3_id} to be promoted, got {rel_data['promoted']['vehicle_id']}"
        print(f"[PASS] POST /release promoted emergency vehicle {v3_id} ahead of earlier normal vehicle! (Cost: INR {rel_data['cost']}, Duration: {rel_data['duration']}h)")

        # Verify history record for user 1 (whose vehicle 1 was completed)
        r_hist = client.get(f"/history/{users[0]['user_id']}")
        assert r_hist.status_code == 200
        hist_data = r_hist.json()
        assert len(hist_data) >= 1, "Expected at least 1 history record for user 1"
        h0 = hist_data[0]
        assert h0["energy_used"] == 25.0
        assert abs(h0["cost"] - expected["total"]) < 0.01, f"History cost mismatch"
        assert h0["user_name"] == "Sparsh"
        assert h0["vehicle_model"] == "Tata Nexon EV"
        assert h0["station_name"] == "Mumbai Central EV Hub"
        print(f"[PASS] Multi-table SQL JOIN verified: User '{h0['user_name']}', Vehicle '{h0['vehicle_model']}', Station '{h0['station_name']}', Cost INR {h0['cost']}")

    print("\n=== ALL AUTOMATED TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    run_tests()
