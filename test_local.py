"""
Quick local test of the agent logic before deploying to AWS.

Requires AWS credentials configured locally (aws configure) with Bedrock
model access enabled for the model in lambda_function.MODEL_ID.

Usage:
    python test_local.py "What's the status of ticket TCK-1002?"
    python test_local.py "How do I request annual leave?"
"""

import sys
from lambda_function import lambda_handler


def main():
    message = " ".join(sys.argv[1:]) or "What's the status of ticket 1001?"
    event = {"message": message}
    result = lambda_handler(event, None)
    print(result["body"])


if __name__ == "__main__":
    main()
