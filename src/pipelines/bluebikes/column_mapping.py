# changing to match 2023/04 schema shift
COLUMN_MAPPING = {
    "tripduration": "trip_duration",
    "starttime": "started_at",
    "stoptime": "ended_at",
    "start station id": "start_station_id",
    "start station name": "start_station_name",
    "start station latitude": "start_lat",
    "start station longitude": "start_lng",
    "end station id": "end_station_id",
    "end station name": "end_station_name",
    "end station latitude": "end_lat",
    "end station longitude": "end_lng",
    "bikeid": "bike_id",
    "usertype": "member_casual",
    "birth year": "birth_year",
    "postal code": "postal_code",
}

FINAL_COLUMNS = [
    "started_at",
    "ended_at",
    "start_station_id",
    "end_station_id",
    "member_casual",
    "birth_year",
    "gender",
    "postal_code",
]

CUSTOMER_MAP = {
    "member": "member",
    "casual": "casual",
    "subscriber": "member",
    "customer": "casual",
}

# https://github.com/ropensci/bikedata
# matching ISO 5218
GENDER_MAP = {"0": "unknown", "1": "male", "2": "female"}
