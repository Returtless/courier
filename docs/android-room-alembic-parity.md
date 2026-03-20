# Alembic vs Room parity (bot/server vs Android)

Goal: capture the schema from Alembic migrations and a checklist to align Room entities in the app.

## Migration chain

- `000` — [alembic/versions/000_initial.py](../alembic/versions/000_initial.py): base tables + `geocode_cache`
- `001` — [alembic/versions/001_add_route_cache.py](../alembic/versions/001_add_route_cache.py): `route_cache`
- `002` — [alembic/versions/002_remove_parking_time.py](../alembic/versions/002_remove_parking_time.py): drop `user_settings.parking_time_minutes`
- `003` — [alembic/versions/003_api_status.py](../alembic/versions/003_api_status.py): `api_status`

Target schema for Room parity: state after `000` then `001` then `002` then `003`.

## Tables (reference)

### orders

`id` PK, `user_id`, `order_date`, names/phone/address, lat/lon, `comment`, time window fields, `status`, `order_number`, `entrance_number`, `apartment_number`, `gis_id`, `created_at`, `updated_at`, `estimated_delivery_time`, `call_time`, `route_order`. Unique `(user_id, order_date, order_number)`.

### start_locations

`id` PK, `user_id`, `location_date`, `location_type`, `address`, lat/lon, `start_time`, timestamps.

### route_data

`id` PK, `user_id`, `route_date`, JSON `route_summary`, `call_schedule`, `route_order`, `total_distance`, `total_time`, `estimated_completion`, timestamps.

### call_status

`id` PK, `user_id`, `order_number`, `call_date`, `call_time`, `arrival_time`, manual flags, `phone`, `customer_name`, `status`, `attempts`, `next_attempt_time`, `confirmation_comment`, timestamps. Unique `(user_id, call_date, order_number)`. Indexes `idx_user_date`, `idx_status_time`.

### user_settings

`id` PK, unique `user_id`, call/service/traffic fields, timestamps. No `parking_time_minutes` after `002`.

### user_credentials

`id` PK, unique `user_id`, `site`, encrypted login/password, timestamps.

### geocode_cache

`id` PK, `address`, lat/lon, `gis_id`, timestamps. Index `idx_address`.

### route_cache (001)

`id` PK, four coords, `distance_km`, `time_minutes`, timestamps. Index `idx_route_coords`.

### api_status (003)

`id` PK, `user_id`, `provider`, `is_available`, `last_check`, `error_message`, `response_time_ms`, timestamps. Unique `(user_id, provider)`.

## Room checklist (fill locally)

Room sources may not be in this repo; verify on your machine:

- [ ] Room `version` matches your migration set for the tables above.
- [ ] Each table has a matching `@Entity` (types as appropriate for Room).
- [ ] Important uniques/indexes match bot behavior where needed.
- [ ] No `parking_time_minutes` on `user_settings` if aligned with `002`.

## Python layout

- ORM: [src/models/order_db.py](../src/models/order_db.py)
- DTO: [src/models/route_types.py](../src/models/route_types.py)
- Barrel: [src/models/order.py](../src/models/order.py) re-exports both for compatibility.
