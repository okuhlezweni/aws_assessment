"""
Load tickets.json into a DynamoDB table.

Usage:
    python load_tickets_to_dynamodb.py [table_name]

Defaults to table name "Tickets" if not given. Assumes the table already
exists (see README / create-table command) and that your local AWS
credentials (aws configure) have dynamodb:PutItem on it.
"""

import json
import sys

# On managed/work machines with local TLS inspection, Python's default
# certificate bundle may not include the company's inspection root CA.
# truststore makes Python use the OS certificate store instead. Safe to
# leave in permanently — no-op on machines that don't need it.
import truststore
truststore.inject_into_ssl()

import boto3

TABLE_NAME = sys.argv[1] if len(sys.argv) > 1 else "Tickets"

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def main():
    with open("tickets.json") as f:
        tickets = json.load(f)

    with table.batch_writer() as batch:
        for ticket_id, fields in tickets.items():
            item = {"ticket_id": ticket_id, **fields}
            batch.put_item(Item=item)
            print(f"Loaded {ticket_id}")

    print(f"\nDone — {len(tickets)} tickets written to '{TABLE_NAME}'.")


if __name__ == "__main__":
    main()
