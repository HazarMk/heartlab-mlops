"""Local-only administrator tool for assigning portal account roles.

Run inside the API container after a user has registered. Docker access is
required; no public API allows users to promote their own account.
"""
from __future__ import annotations

import argparse

from app.portal import DATABASE_PATH, database, initialize_portal_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign a local portal role to an existing account")
    parser.add_argument("--email", required=True, help="Email address used to register")
    parser.add_argument("--role", required=True, choices=("patient", "doctor", "admin", "researcher"))
    args = parser.parse_args()
    initialize_portal_database()
    with database() as connection:
        result = connection.execute(
            "UPDATE portal_accounts SET role = ? WHERE email = ? COLLATE NOCASE",
            (args.role, args.email.strip()),
        )
        if not result.rowcount:
            parser.error(f"No local account found for {args.email!r}; create it in the app first")
    print(f"Role {args.role!r} assigned to {args.email.strip()!r} in {DATABASE_PATH}.")
    print("Ask the user to sign out and sign in again for the new workspace to load.")


if __name__ == "__main__":
    main()
