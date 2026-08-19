"""
Simple CLI entry point that talks to the deployed Lambda Function URL.

Satisfies the "expose the assistant through an API or a simple script/CLI"
requirement without needing a web front-end.

Usage:
    export HELPDESK_URL="https://<your-function-url>.lambda-url.<region>.on.aws/"
    python client.py
"""
import os

# On managed/work machines with local TLS inspection (common antivirus/EDR
# behaviour), Python's default certificate bundle doesn't include the
# company's inspection root CA, causing SSL errors on outgoing HTTPS calls.
# truststore makes Python use the OS certificate store instead, which
# already trusts that root CA on a managed device. Safe to leave this in
# permanently -- it's a no-op on machines that don't need it.
import truststore
truststore.inject_into_ssl()

import requests

FUNCTION_URL = os.environ.get("HELPDESK_URL", "https://ynfu2bleiev5eblpcqifewifey0brsre.lambda-url.us-east-1.on.aws/")


def ask(message: str) -> str:
    if not FUNCTION_URL:
        raise SystemExit("Set HELPDESK_URL environment variable to your Function URL first.")
    resp = requests.post(FUNCTION_URL, json={"message": message}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("answer", resp.text)


def main():
    print("Internal Helpdesk Assistant (type 'exit' to quit)")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue
        print(f"Assistant: {ask(user_input)}")


if __name__ == "__main__":
    main()
