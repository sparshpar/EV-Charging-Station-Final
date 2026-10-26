"""Database Seeding Script for EV Charging Station Manager.
Idempotent: Drops all existing tables and re-populates initial data.
"""

import os
from datetime import datetime
from app.database import engine, SessionLocal, Base
from app.models import User, Vehicle, Station, Slot, Booking, ChargingHistory, Review, Payment
from app import slot_manager, queue_manager


def seed_database():
    # Reset in-memory structures
    slot_manager.clear_slots()
    queue_manager.clear_queue()

    # Drop all and recreate schema
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed Users
        users_data = [
            {"name": "Sparsh", "phone": "9876543210", "email": "sparsh@example.com"},
            {"name": "Aditi", "phone": "9876543211", "email": "aditi@example.com"},
            {"name": "Rohan", "phone": "9876543212", "email": "rohan@example.com"},
            {"name": "Meera", "phone": "9876543213", "email": "meera@example.com"},
        ]
        created_users = []
        for u in users_data:
            user = User(name=u["name"], phone=u["phone"], email=u["email"])
            db.add(user)
            db.commit()
            db.refresh(user)
            created_users.append(user)

        # 2. Seed Vehicles (vehicle_id 1 to 4)
        vehicles_data = [
            {"user_id": created_users[0].user_id, "model": "Tata Nexon EV", "plate_number": "MH04AB1234", "battery_capacity": 40.0},
            {"user_id": created_users[1].user_id, "model": "MG ZS EV", "plate_number": "MH12CD5678", "battery_capacity": 50.0},
            {"user_id": created_users[2].user_id, "model": "Mahindra XEV 9e", "plate_number": "MH01EF9012", "battery_capacity": 59.0},
            {"user_id": created_users[3].user_id, "model": "Hyundai Kona", "plate_number": "MH14GH3456", "battery_capacity": 39.2},
        ]
        created_vehicles = []
        for v in vehicles_data:
            veh = Vehicle(
                user_id=v["user_id"],
                model=v["model"],
                plate_number=v["plate_number"],
                battery_capacity=v["battery_capacity"],
            )
            db.add(veh)
            db.commit()
            db.refresh(veh)
            created_vehicles.append(veh)

        # 3. Seed Stations (15 stations across 3 routes)
        # Location must exactly match the town names
        # price_per_kwh: normal stations 12.0, fast stations 18.0
        stations_spec = [
            # Mumbai -> Pune route (Mumbai, Panvel, Khopoli, Khandala, Lonavala, Pune: 5 slots each)
            {"name": "Mumbai Central EV Hub", "location": "Mumbai", "num_slots": 5, "price_per_kwh": 18.0},
            {"name": "Panvel Express EV Station", "location": "Panvel", "num_slots": 5, "price_per_kwh": 12.0},
            {"name": "Khopoli Ghat Supercharger", "location": "Khopoli", "num_slots": 5, "price_per_kwh": 18.0},
            {"name": "Khandala Heights EV Plaza", "location": "Khandala", "num_slots": 5, "price_per_kwh": 18.0},
            {"name": "Lonavala Hill Charger", "location": "Lonavala", "num_slots": 5, "price_per_kwh": 12.0},
            {"name": "Pune City Gateway EV Hub", "location": "Pune", "num_slots": 5, "price_per_kwh": 18.0},

            # Mumbai -> Surat route (Bhiwandi, Palghar, Vapi, Valsad: 4 slots each, Surat: 5 slots)
            {"name": "Bhiwandi Freight EV Point", "location": "Bhiwandi", "num_slots": 4, "price_per_kwh": 12.0},
            {"name": "Palghar Coastal EV Station", "location": "Palghar", "num_slots": 4, "price_per_kwh": 12.0},
            {"name": "Vapi Highway Station", "location": "Vapi", "num_slots": 4, "price_per_kwh": 18.0},
            {"name": "Valsad Green Port EV", "location": "Valsad", "num_slots": 4, "price_per_kwh": 12.0},
            {"name": "Surat Diamond City EV Hub", "location": "Surat", "num_slots": 5, "price_per_kwh": 18.0},

            # Mumbai -> Goa route (Mahad, Chiplun, Ratnagiri: 4 slots each, Goa: 5 slots)
            {"name": "Mahad Riverbank EV Station", "location": "Mahad", "num_slots": 4, "price_per_kwh": 12.0},
            {"name": "Chiplun Valley Supercharger", "location": "Chiplun", "num_slots": 4, "price_per_kwh": 18.0},
            {"name": "Ratnagiri Konkan EV Hub", "location": "Ratnagiri", "num_slots": 4, "price_per_kwh": 12.0},
            {"name": "Goa Sunshine EV Terminal", "location": "Goa", "num_slots": 5, "price_per_kwh": 18.0},
        ]

        station_count = 0
        created_stations = []
        for s_info in stations_spec:
            station = Station(
                name=s_info["name"],
                location=s_info["location"],
                num_slots=s_info["num_slots"],
                price_per_kwh=s_info.get("price_per_kwh", 15.0),
            )
            db.add(station)
            db.commit()
            db.refresh(station)
            station_count += 1
            created_stations.append(station)

            # Seed slots: mix normal and fast
            for i in range(s_info["num_slots"]):
                slot_type = "fast" if (i % 2 == 1) else "normal"
                slot = Slot(
                    station_id=station.station_id,
                    slot_type=slot_type,
                    status="free",
                )
                db.add(slot)
                db.commit()
                db.refresh(slot)

                # Register in in-memory Data Structure
                slot_manager.register_slot(slot.slot_id, station.station_id, "free")

        # 4. Seed a few initial demo reviews
        demo_reviews = [
            {"station_id": created_stations[0].station_id, "vehicle_id": created_vehicles[0].vehicle_id, "rating": 5, "comment": "Fast 150kW chargers, clean lounge!"},
            {"station_id": created_stations[0].station_id, "vehicle_id": created_vehicles[1].vehicle_id, "rating": 5, "comment": "Seamless auto-promotion from queue."},
            {"station_id": created_stations[1].station_id, "vehicle_id": created_vehicles[2].vehicle_id, "rating": 4, "comment": "Good location right off the expressway."},
            {"station_id": created_stations[2].station_id, "vehicle_id": created_vehicles[3].vehicle_id, "rating": 5, "comment": "Great stop before the ghat section."},
        ]
        for rev in demo_reviews:
            r = Review(
                station_id=rev["station_id"],
                vehicle_id=rev["vehicle_id"],
                rating=rev["rating"],
                comment=rev["comment"],
                created_at=datetime.now()
            )
            db.add(r)
        db.commit()

        print(f"Seeded {station_count} stations across 3 routes, {len(created_users)} users, {len(created_vehicles)} vehicles.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
