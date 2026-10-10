# WOMS Work Order API: Integration Guide v2.3

*Northwind Facility Services, IT Applications. Last revised 2021-03.*

> **Engagement note (ours, not Northwind's):** this is the guide as the customer handed it over.
> Two statements below are false, and a third is misleading. They are marked in `../discovery-notes.md`,
> not here, because the point of a customer document is that you receive it as it is.

## 1. Overview

The WOMS API gives read access to work orders for reporting and integration partners. It is read-only.
Write access is not offered to third parties.

## 2. Authentication

Integration partners receive a service account from IT Security. Requests without valid credentials receive
`401 Unauthorized`.

## 3. Listing work orders

```
GET /api/v2/workorders?offset=<n>&limit=<m>
```

| Parameter | Default | Max | Notes |
|---|---|---|---|
| `offset` | 0 | — | Zero-based position in the result set |
| `limit` | 50 | 200 | Records per page |

Results are returned newest first, in a stable order, so a client may page through the full set by
increasing `offset` until a page shorter than `limit` is returned.

Under heavy load the API may return `503 Service Unavailable`. Clients should retry.

## 4. The work order record

| Field | Type | Description |
|---|---|---|
| `wo_id` | string | Work order number. Unique across the system. |
| `region` | string | Dispatch region: `EAST`, `METRO`, `CENTRAL` |
| `opened_at` | string | Time the work order was opened. All timestamps are UTC. |
| `status` | string | See section 5 |
| `priority` | string | `P1` (emergency) to `P4` (routine) |
| `trade` | string | `HVAC`, `PLUMBING`, `ELECTRICAL`, `ELEVATOR`, `GENERAL` |
| `site` | string | Street address of the site |
| `description` | string | Free text entered at intake |

## 5. Status codes

| Code | Meaning |
|---|---|
| `O` | Open |
| `A` | Assigned to a technician |
| `C` | Closed |

## 6. Nightly export

A CSV export of all work orders is written to the integration share at 06:00 UTC daily, with the same
fields as the API.
