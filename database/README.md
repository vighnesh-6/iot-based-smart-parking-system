# Runtime database location

This directory documents storage policy; it must not hold the live database.

Use `%LOCALAPPDATA%\SmartParking\parking.db` on Windows, outside the
OneDrive-synchronized project. The `.env.example` template uses
`${LOCALAPPDATA}/SmartParking/parking.db` for python-dotenv expansion during
the future backend setup. The future backend must resolve an absolute path.

No database or schema has been created in this scaffolding stage. Create the
runtime directory and schema only during the persistence implementation stage.
Back up a running SQLite database with a consistent backup method, or stop it
cleanly before exporting; do not synchronize an open database and its journals.

Live database files and journals are ignored by Git. Synthetic ML history
belongs in `ml/data/`, with explicit source metadata, not in live readings.
