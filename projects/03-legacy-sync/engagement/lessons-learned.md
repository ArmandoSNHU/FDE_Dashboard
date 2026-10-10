# Lessons learned

Each one names what happened and what it changed. It's not a list of things that went well.

## 1. The customer's documentation is a hypothesis

The API guide was wrong about IDs, time zones and paging stability, and the data dictionary was missing a
status code. All of it surfaced in an hour at Ray's desk, none of it in the documents. **Changed:** WOMS's real
behaviour was reproduced and pinned by tests *before* the sync was built against it, so every rule in the
code traces back to something observed.

## 2. The request is rarely the problem

"Get the tickets in" would have been met by copying the rows, status letters and all, and it would have
shipped the July incident (a closed ticket read as cancelled) to the on-call view at scale. Restating the
problem as *trust in ticket status* is what made "reject, don't guess" an acceptance criterion instead of a
nice-to-have.

## 3. Our own platform had gaps too

The platform could write incidents but not read them (I1), had no status column (I2), and graded severity in
two vocabularies (I3). The third was found by running the demo, not by a test: an alert built from an incident
was refused. **Changed:** the demo is part of CI on both operating systems, so a seam between components
fails a build, not a customer conversation.

## 4. A spike beats a debate

CR-001 could have been argued for a week. Half a day of throwaway code showed that 60 of 60 spreadsheet rows
were ambiguous on the obvious key. The decision, and the one-column fix on Northwind's side, followed directly.

## 5. Small platform habits matter on someone else's machine

Python's `sqlite3` context manager commits but doesn't close the file, and Windows won't delete an open file.
The demo crashed in cleanup until connections were closed explicitly. It's the same lesson as project 01's
post-mortem: verify where the customer runs it, not where you wrote it.
