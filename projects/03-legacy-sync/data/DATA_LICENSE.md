# Data source and terms

`nyc311_sample.csv` is a sample of real records from **311 Service Requests from 2020 to Present**
(NYC Open Data, dataset `erm2-nwe9`), published by the City of New York.

- **Retrieved:** 2026-10-10 by `scripts/fetch_sample.py` from `https://data.cityofnewyork.us/resource/erm2-nwe9.json`
- **Query:** for each of the five boroughs, the first 50 records by `created_date` in each of two windows,
  2024-06-17 to 2024-07-01 and 2024-07-01 to 2024-07-15, restricted to the complaint types in
  `src/fde_sync/trades.py` and to records with an address and a descriptor. 500 records.
- **Columns kept:** `unique_key, created_date, closed_date, complaint_type, descriptor, status,
  incident_address, borough`.

## Terms

NYC's Open Data Law (Local Law 11 of 2012) makes public data sets available "without any registration
requirement, license requirement or restrictions on their use", and allows the City to ask that anyone
republishing a data set identify its source and version and describe any changes. Source and version are
above; the changes are below. The City makes no warranty about the data's completeness or accuracy.

## What this project changes

The records stay as downloaded in this file. The mock legacy system (`src/fde_sync/legacy/`) then turns them
into a fictional company's work orders:

- borough → Northwind region, complaint type → trade (`src/fde_sync/trades.py`);
- the work-order status is derived from the real `closed_date` as of a fictional export at
  2024-07-15 06:00 UTC, with a seeded share marked cancelled;
- priority is assigned by a seeded rule from complaint type and descriptor;
- the five documented quirks (design §5) and a handful of deliberately bad records are injected.

Northwind Facility Services, its regions and its people are fictional. Nothing here describes the City of
New York's handling of these requests.
