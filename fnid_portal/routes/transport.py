"""
Transport Module Routes

Fleet management, trip logging, fuel tracking, and service scheduling
for the FNID Area 3 vehicle pool.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import generate_id, get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("transport", __name__, url_prefix="/transport")

VEHICLE_TYPES = ["Sedan", "SUV", "Pickup Truck", "Motorcycle", "Bus/Coaster", "Flatbed"]
VEHICLE_STATUSES = ["Available", "In Use", "Maintenance", "Decommissioned"]


@bp.route("/")
@login_required
@permission_required("transport", "read")
def fleet():
    """Vehicle fleet list with status indicators."""
    conn = get_db()
    try:
        vehicles = conn.execute(
            "SELECT * FROM transport_vehicles ORDER BY status, vehicle_id"
        ).fetchall()

        available = sum(1 for v in vehicles if v["status"] == "Available")
        in_use = sum(1 for v in vehicles if v["status"] == "In Use")
        maintenance = sum(1 for v in vehicles if v["status"] == "Maintenance")

        return render_template(
            "transport/fleet.html",
            vehicles=vehicles,
            available=available,
            in_use=in_use,
            maintenance=maintenance,
        )
    finally:
        conn.close()


@bp.route("/vehicle/<vehicle_id>")
@login_required
@permission_required("transport", "read")
def vehicle_detail(vehicle_id):
    """Show vehicle detail, trip history, and service log."""
    conn = get_db()
    try:
        vehicle = conn.execute(
            "SELECT * FROM transport_vehicles WHERE vehicle_id = ?", (vehicle_id,)
        ).fetchone()
        if not vehicle:
            flash("Vehicle not found.", "danger")
            return redirect(url_for("transport.fleet"))

        trips = conn.execute(
            "SELECT * FROM transport_trips WHERE vehicle_id = ? ORDER BY created_at DESC",
            (vehicle_id,),
        ).fetchall()

        return render_template(
            "transport/vehicle_detail.html",
            vehicle=vehicle,
            trips=trips,
        )
    finally:
        conn.close()


@bp.route("/vehicle/new", methods=["GET", "POST"])
@login_required
@permission_required("transport", "create")
def new_vehicle():
    """Add a new vehicle to the fleet."""
    if request.method == "POST":
        conn = get_db()
        try:
            vehicle_id = generate_id("VEH", "transport_vehicles", "vehicle_id")
            now = datetime.now().isoformat()
            name = current_user.full_name

            conn.execute("""
                INSERT INTO transport_vehicles
                (vehicle_id, registration, make, model, year, vehicle_type,
                 assigned_unit, assigned_officer, status, current_mileage,
                 last_service_date, next_service_due, defects, notes,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vehicle_id,
                request.form.get("registration", ""),
                request.form.get("make", ""),
                request.form.get("model", ""),
                request.form.get("year", ""),
                request.form.get("vehicle_type", ""),
                request.form.get("assigned_unit", ""),
                request.form.get("assigned_officer", ""),
                request.form.get("status", "Available"),
                request.form.get("current_mileage", 0),
                request.form.get("last_service_date", ""),
                request.form.get("next_service_due", ""),
                request.form.get("defects", ""),
                request.form.get("notes", ""),
                now,
                now,
            ))
            conn.commit()

            log_audit("transport_vehicles", vehicle_id, "CREATE",
                      current_user.badge_number, name,
                      f"New vehicle added: {request.form.get('registration')}")

            flash(f"Vehicle {vehicle_id} added successfully.", "success")
            return redirect(url_for("transport.vehicle_detail", vehicle_id=vehicle_id))

        except Exception as e:
            conn.rollback()
            flash(f"Error adding vehicle: {e}", "danger")
        finally:
            conn.close()

    return render_template(
        "transport/vehicle_form.html",
        vehicle=None,
        is_new=True,
        vehicle_types=VEHICLE_TYPES,
        vehicle_statuses=VEHICLE_STATUSES,
    )


@bp.route("/vehicle/<vehicle_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("transport", "update")
def edit_vehicle(vehicle_id):
    """Edit vehicle details, maintenance status, and defects."""
    conn = get_db()
    try:
        vehicle = conn.execute(
            "SELECT * FROM transport_vehicles WHERE vehicle_id = ?", (vehicle_id,)
        ).fetchone()
        if not vehicle:
            flash("Vehicle not found.", "danger")
            return redirect(url_for("transport.fleet"))

        if request.method == "POST":
            now = datetime.now().isoformat()
            name = current_user.full_name

            conn.execute("""
                UPDATE transport_vehicles SET
                    registration = ?, make = ?, model = ?, year = ?,
                    vehicle_type = ?, assigned_unit = ?, assigned_officer = ?,
                    status = ?, current_mileage = ?,
                    last_service_date = ?, next_service_due = ?,
                    defects = ?, notes = ?, updated_at = ?
                WHERE vehicle_id = ?
            """, (
                request.form.get("registration", ""),
                request.form.get("make", ""),
                request.form.get("model", ""),
                request.form.get("year", ""),
                request.form.get("vehicle_type", ""),
                request.form.get("assigned_unit", ""),
                request.form.get("assigned_officer", ""),
                request.form.get("status", "Available"),
                request.form.get("current_mileage", 0),
                request.form.get("last_service_date", ""),
                request.form.get("next_service_due", ""),
                request.form.get("defects", ""),
                request.form.get("notes", ""),
                now,
                vehicle_id,
            ))
            conn.commit()

            log_audit("transport_vehicles", vehicle_id, "UPDATE",
                      current_user.badge_number, name,
                      f"Vehicle updated: {request.form.get('registration')}")

            flash(f"Vehicle {vehicle_id} updated.", "success")
            return redirect(url_for("transport.vehicle_detail", vehicle_id=vehicle_id))

        return render_template(
            "transport/vehicle_form.html",
            vehicle=vehicle,
            is_new=False,
            vehicle_types=VEHICLE_TYPES,
            vehicle_statuses=VEHICLE_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/trips")
@login_required
@permission_required("transport", "read")
def trip_log():
    """All trips, filterable by date range and vehicle."""
    conn = get_db()
    try:
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        vehicle_filter = request.args.get("vehicle_id", "")

        query = "SELECT * FROM transport_trips WHERE 1=1"
        params = []

        if date_from:
            query += " AND trip_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND trip_date <= ?"
            params.append(date_to)
        if vehicle_filter:
            query += " AND vehicle_id = ?"
            params.append(vehicle_filter)

        query += " ORDER BY created_at DESC"
        trips = conn.execute(query, params).fetchall()

        vehicles = conn.execute(
            "SELECT vehicle_id, registration, make, model FROM transport_vehicles ORDER BY vehicle_id"
        ).fetchall()

        return render_template(
            "transport/trip_log.html",
            trips=trips,
            vehicles=vehicles,
            date_from=date_from,
            date_to=date_to,
            vehicle_filter=vehicle_filter,
        )
    finally:
        conn.close()


@bp.route("/trips/new", methods=["GET", "POST"])
@login_required
@permission_required("transport", "create")
def new_trip():
    """Log a new trip with auto-calculated mileage delta."""
    conn = get_db()
    try:
        if request.method == "POST":
            trip_id = generate_id("TRIP", "transport_trips", "trip_id")
            now = datetime.now().isoformat()
            name = current_user.full_name
            vehicle_id = request.form.get("vehicle_id", "")
            start_mileage = request.form.get("start_mileage", "")

            conn.execute("""
                INSERT INTO transport_trips
                (trip_id, vehicle_id, driver_badge, driver_name, trip_date,
                 purpose, linked_case_id, linked_op_id,
                 departure_location, destination, departure_time,
                 start_mileage, fuel_added_litres, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trip_id,
                vehicle_id,
                request.form.get("driver_badge", ""),
                request.form.get("driver_name", ""),
                request.form.get("trip_date", ""),
                request.form.get("purpose", ""),
                request.form.get("linked_case_id", ""),
                request.form.get("linked_op_id", ""),
                request.form.get("departure_location", ""),
                request.form.get("destination", ""),
                request.form.get("departure_time", ""),
                start_mileage,
                request.form.get("fuel_added_litres", ""),
                request.form.get("notes", ""),
                now,
            ))

            # Mark vehicle as In Use
            conn.execute(
                "UPDATE transport_vehicles SET status = 'In Use', updated_at = ? WHERE vehicle_id = ?",
                (now, vehicle_id),
            )

            conn.commit()

            log_audit("transport_trips", trip_id, "CREATE",
                      current_user.badge_number, name,
                      f"Trip logged for vehicle {vehicle_id}")

            flash(f"Trip {trip_id} logged successfully.", "success")
            return redirect(url_for("transport.trip_log"))

        vehicles = conn.execute(
            "SELECT * FROM transport_vehicles WHERE status IN ('Available', 'In Use') ORDER BY vehicle_id"
        ).fetchall()

        return render_template(
            "transport/trip_form.html",
            vehicles=vehicles,
        )
    finally:
        conn.close()


@bp.route("/trips/<trip_id>/return", methods=["POST"])
@login_required
@permission_required("transport", "update")
def return_trip(trip_id):
    """Mark trip as returned: set return_time, end_mileage, update vehicle mileage."""
    conn = get_db()
    try:
        trip = conn.execute(
            "SELECT * FROM transport_trips WHERE trip_id = ?", (trip_id,)
        ).fetchone()
        if not trip:
            flash("Trip not found.", "danger")
            return redirect(url_for("transport.trip_log"))

        now = datetime.now()
        name = current_user.full_name
        return_time = request.form.get("return_time", now.strftime("%H:%M"))
        end_mileage = request.form.get("end_mileage", "")
        fuel_added = request.form.get("fuel_added_litres", "")

        update_fields = "return_time = ?"
        update_params = [return_time]

        if end_mileage:
            update_fields += ", end_mileage = ?"
            update_params.append(end_mileage)

        if fuel_added:
            update_fields += ", fuel_added_litres = ?"
            update_params.append(fuel_added)

        update_params.append(trip_id)
        conn.execute(
            f"UPDATE transport_trips SET {update_fields} WHERE trip_id = ?",
            update_params,
        )

        # Update vehicle current_mileage and set status back to Available
        if end_mileage:
            conn.execute(
                "UPDATE transport_vehicles SET current_mileage = ?, "
                "status = 'Available', updated_at = ? "
                "WHERE vehicle_id = ?",
                (end_mileage, now.isoformat(), trip["vehicle_id"]),
            )
        else:
            conn.execute(
                "UPDATE transport_vehicles SET status = 'Available', updated_at = ? WHERE vehicle_id = ?",
                (now.isoformat(), trip["vehicle_id"]),
            )

        conn.commit()

        log_audit("transport_trips", trip_id, "RETURN",
                  current_user.badge_number, name,
                  f"Trip returned, end mileage: {end_mileage}")

        flash(f"Trip {trip_id} marked as returned.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("transport.trip_log"))


@bp.route("/service")
@login_required
@permission_required("transport", "read")
def service_log():
    """Vehicles due for service."""
    conn = get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        # Vehicles with upcoming or overdue service
        vehicles = conn.execute("""
            SELECT * FROM transport_vehicles
            WHERE next_service_due IS NOT NULL AND next_service_due != ''
            ORDER BY
                CASE WHEN next_service_due <= ? THEN 0 ELSE 1 END,
                next_service_due ASC
        """, (today,)).fetchall()

        return render_template(
            "transport/fleet.html",
            vehicles=vehicles,
            available=0,
            in_use=0,
            maintenance=0,
            service_view=True,
            today=today,
        )
    finally:
        conn.close()


@bp.route("/fuel")
@login_required
@permission_required("transport", "read")
def fuel_report():
    """Fuel consumption summary by vehicle."""
    conn = get_db()
    try:
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")

        query = """
            SELECT
                t.vehicle_id,
                v.registration,
                v.make,
                v.model,
                COUNT(t.id) AS trip_count,
                COALESCE(SUM(CASE WHEN t.end_mileage AND t.start_mileage
                    THEN t.end_mileage - t.start_mileage ELSE 0 END), 0) AS total_km,
                COALESCE(SUM(CASE WHEN t.fuel_added_litres != '' AND t.fuel_added_litres IS NOT NULL
                    THEN CAST(t.fuel_added_litres AS REAL) ELSE 0 END), 0) AS total_fuel
            FROM transport_trips t
            LEFT JOIN transport_vehicles v ON t.vehicle_id = v.vehicle_id
            WHERE 1=1
        """
        params = []

        if date_from:
            query += " AND t.trip_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND t.trip_date <= ?"
            params.append(date_to)

        query += " GROUP BY t.vehicle_id ORDER BY total_fuel DESC"
        fuel_data = conn.execute(query, params).fetchall()

        return render_template(
            "transport/fuel_report.html",
            fuel_data=fuel_data,
            date_from=date_from,
            date_to=date_to,
        )
    finally:
        conn.close()
