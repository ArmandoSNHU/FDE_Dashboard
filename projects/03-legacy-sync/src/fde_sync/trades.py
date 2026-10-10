"""How a 311 complaint type becomes a Northwind trade.

The sample is real NYC 311 data; Northwind is fictional. This table is the one place
the two meet, so a category we can't map is filtered out at fetch time, not guessed later.
"""

TRADE_BY_COMPLAINT = {
    "HEAT/HOT WATER": "HVAC",
    "PLUMBING": "PLUMBING",
    "WATER LEAK": "PLUMBING",
    "ELECTRIC": "ELECTRICAL",
    "Elevator": "ELEVATOR",
    "DOOR/WINDOW": "GENERAL",
    "PAINT/PLASTER": "GENERAL",
    "APPLIANCE": "GENERAL",
}

# Fictional: Northwind runs three regions, and Staten Island's sites are dispatched
# from a Chicago office, which is what gives the sample two time zones.
REGION_BY_BOROUGH = {
    "MANHATTAN": "EAST",
    "BRONX": "EAST",
    "BROOKLYN": "METRO",
    "QUEENS": "METRO",
    "STATEN ISLAND": "CENTRAL",
}

TIMEZONE_BY_REGION = {
    "EAST": "America/New_York",
    "METRO": "America/New_York",
    "CENTRAL": "America/Chicago",
}
