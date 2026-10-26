# EV Charging Station Manager (College Capstone Project)

An end-to-end college capstone project demonstrating **DBMS**, **Data Structures**, and **Python Logic** working together in a real-world EV charging and queue scheduling platform.

---

## 1. Technologies Used (Frontend & Backend Stack)

### Backend Architecture
- **Language & Runtime**: Python 3.12
- **Web Framework**: **FastAPI** (asynchronous, high-performance REST API with OpenAPI/Swagger autogeneration)
- **ASGI Server**: **Uvicorn**
- **ORM & Database Abstraction**: **SQLAlchemy 2.x** with declarative data models
- **Database Engine**: **SQLite** (`ev_charging.db`), enforcing referential integrity with `PRAGMA foreign_keys=ON`
- **Data Validation & Serialization**: **Pydantic v2** (`BaseModel`, `ConfigDict`)
- **Data Structures**:
  - **In-Memory Dictionary / Hash Map ($O(1)$)** for instant slot state lookups (`app/slot_manager.py`)
  - **Binary Min-Heap ($O(\log n)$)** via Python `heapq` for priority queue scheduling (`app/queue_manager.py`)
  - **Heap Mutation ($O(n)$)** via `heapq.heapify` for in-place leave-queue cancellation

### Frontend Architecture
- **Structure**: Vanilla **HTML5** & semantic components (no heavy node_modules build step required)
- **Styling**: Modern responsive **CSS3** with CSS custom properties (variables), iOS-style rounded containers, card elevations, and custom responsive layouts
- **Interactive Logic**: Vanilla **JavaScript (ES6+)** with asynchronous `fetch()` API and reactive UI state management
- **Geographic Mapping**: **Leaflet.js 1.9.4** with OpenStreetMap tiles, custom SVG circular pins, and live polyline paths
- **UPI QR Code Generation**: **QRCode.js** (client-side dynamic vector QR rendering)
- **Typography & Icons**: Plus Jakarta Sans / Inter via Google Fonts, FontAwesome 6 icons

### Running 100% Offline on Any Laptop
This project is engineered to run completely offline on any standard laptop:
1. **Zero Cloud Database Dependencies**: Uses embedded SQLite (`ev_charging.db`). No cloud accounts, Postgres, or MySQL servers required.
2. **Zero External Paid APIs**: Google Maps navigation uses standard web intents (`https://www.google.com/maps/dir/?api=1&...`), GPS uses the browser's built-in `navigator.geolocation` API, and pricing math runs 100% locally in Python.
3. **Local In-Memory Cache**: All station coordinates, tariffs, and slot states are hydrated locally into Python memory on startup.

---

## 2. How This Proves DBMS + DS + Python

| Pillar | Implementation Component | Technical Proof & Grading Justification |
| :--- | :--- | :--- |
| **DBMS** | SQLAlchemy 2.x + SQLite (`ev_charging.db`) | • **Relational Schema**: 8 normalized tables (`users`, `vehicles`, `stations`, `slots`, `bookings`, `charging_history`, `payments`, `reviews`).<br>• **Foreign Keys & Referential Integrity**: Real FK constraints enforced via SQLite `PRAGMA foreign_keys=ON` on vehicle, slot, booking, payment, review, and history records.<br>• **Multi-Table Relational JOINs**: `GET /history/vehicle/{vehicle_id}/summary` and `GET /history/vehicle/{vehicle_id}` execute a 5-table SQL JOIN spanning `ChargingHistory` ⨝ `Booking` ⨝ `Slot` ⨝ `Station` ⟕ `Payment`.<br>• **Aggregations & Grouping**: SQL `SUM`, `COUNT`, and station grouping for visit histories, session counts, and revenue statistics. |
| **Data Structures** | In-Memory Dict + Heapq Priority Queue | • **Hash Map / Dict ($O(1)$ Lookup)**: `app/slot_manager.py` maintains `slot_status` (`slot_id` $\rightarrow$ `"free"`/`"occupied"`) and `slot_station` (`slot_id` $\rightarrow$ `station_id`). Sub-millisecond slot queries before hitting the DB.<br>• **Binary Min-Heap ($O(\log n)$ Push/Pop)**: `app/queue_manager.py` uses Python `heapq` with tuple ordering `(priority, arrival_time, seq)`. Emergency ($0$) jumps ahead of Fast ($1$) and Normal ($2$), while preserving FCFS timestamp ordering within the same tier.<br>• **Heap Mutation & Re-indexing ($O(n)$ Heapify)**: `remove_vehicle(vehicle_id)` filters the internal heap array in-place when a queued driver leaves line, rebuilding the binary heap invariant with `heapq.heapify()`. |
| **Python Logic** | FastAPI + Business Rules Engine | • **Single Source of Truth Pricing Engine**: `app/pricing.py` contains all tariffs, charger powers, and tax formulas. The frontend never hardcodes prices and always queries `/estimate`.<br>• **In-Memory Decision Before Persistence**: Slot availability is decided in $O(1)$ memory; only confirmed state changes are written to SQLite.<br>• **Automatic Priority Promotion**: Slot release or cancellation automatically pops the highest-priority vehicle from the min-heap and provisions its active booking.<br>• **Corridor Walking Algorithm**: Greedy simulation evaluating battery discharge and recommending optimal charging stops along highway corridors before battery drops below 15%. |

---

## 3. Priority-Based Pricing Model (`app/pricing.py`)

All prices, fees, and calculations are defined in Python as the single source of truth:

```python
TARIFF = {
    "normal":    {"rate_per_kwh": 12.0, "booking_fee": 0.0},
    "fast":      {"rate_per_kwh": 18.0, "booking_fee": 10.0},
    "emergency": {"rate_per_kwh": 25.0, "booking_fee": 30.0},
}
CHARGER_POWER_KW = {"normal": 22.0, "fast": 50.0}   # affects charging duration only
TAX_PERCENT = 5.0                                    # demo GST constant
```

### Mathematical Formulas
1. $\text{Energy Cost} = \text{kWh} \times \text{Rate Per kWh}$
2. $\text{Tax (GST 5\%)} = (\text{Energy Cost} + \text{Booking Fee}) \times \frac{5}{100}$
3. $\text{Total Amount} = \text{Energy Cost} + \text{Booking Fee} + \text{Tax}$
4. $\text{Charging Time} = \frac{\text{kWh}}{\text{Charger Power (kW)}} \times 60 \text{ min}$

---

## 4. Feature Matrix

### 1. Priority-Based Pricing
- Single source of truth in `app/pricing.py`.
- Emergency priority visibly costs more with transparent UI explanation (*"Emergency: priority access, higher tariff"*).
- Estimated cost is calculated and attached to `Booking` at reservation time, and final itemized cost is committed to `ChargingHistory`.

### 2. Standalone Charging Cost Calculator
- Accessible via the **Calc** tab on the bottom dock.
- Allows drivers to pick current battery %, target battery %, and target station.
- Shows real-time cost breakdown (Energy, Rate, Fee, 5% Tax, Total, Time).
- Side-by-side comparison table showing **Normal vs Fast vs Emergency** for the exact same charge, highlighting the cheapest tier in green.
- Reused directly on the station detail screen before booking.

### 3. UPI Payment Flow (Demo Mode)
- **Demo Mode Banner**: Clear label explaining that payment simulation does not transfer real funds.
- **Three Payment Methods**:
  1. **UPI App Deep Link**: `upi://pay?pa=...` opens mobile UPI apps (GPay, PhonePe, Paytm).
  2. **Live Dynamic QR Code**: Rendered via `QRCode.js` with embedded amount and merchant ID.
  3. **UPI ID Entry & Simulation**: Validates `name@bank` format, triggers a 2-second processing animation, and calls `POST /payments`.
- Rejects wrong amounts or duplicate payments on the same booking.
- Generates official `UPI` + 12-digit transaction references.
- Unpaid sessions display as *"Payment pending"* in History with an interactive *"Pay now"* button.

### 4. GPS Navigation & Live Tracking
- **Google Maps Intent**: "Navigate" button opens turn-by-turn directions directly in Google Maps (`https://www.google.com/maps/dir/?api=1&...`).
- **Live In-App Tracking**: `navigator.geolocation.watchPosition` renders a pulsing blue driver marker and dashed polyline to the station.
- Live distance display: *"X km away, about Y min (estimated @ 50 km/h)"*.
- Geofence arrival alert: Displays *"You've arrived at the station!"* banner within 150 meters.
- Graceful fallback note if location permissions are denied.

### 5. Smarter Charging History & Visual Analytics
- Top metric cards: **Times charged**, **Total spent (₹)**, and **Total energy (kWh)**.
- **"Where You Charged" Section**:
  - Interactive Leaflet map with **numbered circular markers** displaying the exact visit count at each station.
  - Ranked station visit breakdown table sorted by most visits.
- **Itemized Session List**: Shows date, station, priority badge, cost, and payment status (Paid vs. Payment pending).
- Clicking any session expands a comprehensive digital receipt dialog with tax, fee, and UPI reference.

### 6. Operations Dashboard Enhancements (`index.html`)
- Total revenue metric summing all confirmed UPI payments.
- Paid vs. pending session counter.
- **Revenue Split by Priority**: Visual proportional horizontal bar graph across Normal, Fast, and Emergency tiers.
- **Busiest Stations Ranking**: Top stations ranked by total session volume and revenue.
- Automatic 5-second asynchronous polling.

---

## 5. REST API Documentation

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Health check confirmation |
| `GET` | `/stations` | All 15 stations with live free slot counts, price/kWh, and ratings |
| `GET` | `/stations/{station_id}` | Station detail with fast/normal breakdown and queue length |
| `POST` | `/estimate` | Computes dynamic energy, tax, fee, total, and comparison across tiers |
| `POST` | `/book` | Reserve a slot ($O(1)$) or enter priority queue ($O(\log n)$) |
| `POST` | `/release/{slot_id}` | Release slot, calculate final cost, log history, and auto-promote next EV |
| `POST` | `/cancel/{booking_id}` | Cancel active session, free slot, and promote waiting vehicle |
| `POST` | `/queue/leave/{vehicle_id}` | Leave waiting line, filter heap array and rebuild heap invariant |
| `GET` | `/queue/position/{vehicle_id}` | Current queue position and wait estimate |
| `GET` | `/bookings/vehicle/{vehicle_id}/active` | Retrieve active session for a vehicle (turn alert detection) |
| `POST` | `/payments` | Process demo UPI payment; verifies amount and generates UPI reference |
| `GET` | `/payments/{booking_id}` | Retrieve payment record for a booking |
| `GET` | `/history/vehicle/{vehicle_id}/summary` | Multi-table JOIN summary: sessions, energy, total spent, by_station map |
| `GET` | `/history/vehicle/{vehicle_id}` | Itemized charging sessions for a vehicle with payment status |
| `GET` | `/admin/revenue` | Revenue metrics, paid/pending counts, priority breakdown, busiest stations |

---

## 6. Step-by-Step Setup and Execution Guide

### Step 1: Open PowerShell in Project Directory
```powershell
cd C:\Users\HP\.gemini\antigravity\scratch\ev-charging-manager
```

### Step 2: Seed the Database
```powershell
python seed.py
```
> **Expected Output**: `Seeded 15 stations across 3 routes, 4 users, 4 vehicles.`

### Step 3: Start the Backend API (Terminal 1)
```powershell
uvicorn app.main:app --reload --port 8000
```
> **Expected Output**: `Uvicorn running on http://127.0.0.1:8000. Hydrated 68 slots into memory slot_manager.`

### Step 4: Start Frontend HTTP Server (Terminal 2)
```powershell
cd C:\Users\HP\.gemini\antigravity\scratch\ev-charging-manager\frontend
python -m http.server 5500
```

### Step 5: Open the Applications
- **Driver Mobile App**: [http://127.0.0.1:5500/mobile.html](http://127.0.0.1:5500/mobile.html)
- **Admin Operations Dashboard**: [http://127.0.0.1:5500/index.html](http://127.0.0.1:5500/index.html)
- **FastAPI Interactive Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 7. Running Verification Test Suites

All capstone requirements are verified with automated test suites:
```powershell
# 1. Foundational DBMS & Data Structure Tests
python test_app.py

# 2. Priority Queue, Cancel, Leave Queue, and Reviews Tests
python test_tier_backend.py

# 3. Priority Pricing, UPI Payments, and History Summary Tests
python test_features.py

# 4. Frontend DOM ID & JavaScript Syntax Integrity Check
python verify_syntax.py
```
*(All 4 test suites pass with 0 errors.)*
