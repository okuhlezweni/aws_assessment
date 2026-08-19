"""
Internal Helpdesk Assistant — AWS Lambda handler.

This single Lambda function:
  1. Receives a user's question (via Function URL / API Gateway / direct invoke).
  2. Calls Amazon Bedrock (Claude) with a system prompt + a tool definition.
  3. If Claude decides it needs the tool, this Lambda runs the tool logic itself
     (ticket lookup against a mock JSON "database") and sends the result back
     to Claude for a final natural-language answer.
  4. Returns the assistant's final answer as JSON.

Why one Lambda instead of a Lambda calling another Lambda?
  The assessment only requires that "tool logic runs in Lambda" — it doesn't
  require a separate Lambda per tool. Keeping the orchestration and the tool
  in the same function is simpler to deploy, test, and explain, at the cost of
  being less modular. If this were a real production system with many tools,
  I'd split each tool into its own Lambda behind the action group / router.
"""

import json
import os
import boto3

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Claude Haiku 4.5 on Bedrock: cheap, fast, more than capable for a helpdesk
# assistant that mostly does routing + short answers. (Originally built against
# Claude 3.5 Haiku, which Bedrock has since retired to Legacy status -- worth
# a line in the write-up about model deprecation as a real-world constraint.)
# Swap this for another Bedrock model ID if you want to compare behaviour/cost.
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# Real data store: DynamoDB table "Tickets" (partition key: ticket_id).
# See load_tickets_to_dynamodb.py for how the mock data was loaded in.
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
tickets_table = dynamodb.Table(os.environ.get("TICKETS_TABLE_NAME", "Tickets"))

# Fallback prompt used only if SYSTEM_PROMPT_ARN isn't set (e.g. running
# test_local.py without Bedrock Prompt Management configured). The
# source-of-truth version lives in Bedrock Prompt Management — see README.
_FALLBACK_SYSTEM_PROMPT = """You are the Internal Helpdesk Assistant for a small company.

Your job:
- Answer general IT/HR/workplace questions helpfully and concisely, in a friendly,
  professional tone.
- When a user asks about the status of a specific support ticket, you MUST use the
  lookup_ticket tool rather than guessing or making up a status. Only call it when
  a ticket ID is given or clearly implied.
- Ticket IDs look like "TCK-1001". If the user gives a number without the TCK- prefix,
  normalise it before calling the tool.
- If a ticket ID is not found, say so clearly and suggest the user double-check the ID
  or contact IT support directly — do not invent ticket details.
- If a question is outside your scope (e.g. medical advice, legal advice, anything
  unrelated to workplace/IT support), politely say it's outside what you can help with.
- Keep answers short. This is a helpdesk chat, not an essay.
"""


def _load_system_prompt() -> str:
    """
    Fetch the system prompt from Bedrock Prompt Management if configured,
    otherwise fall back to the hardcoded copy above.

    Runs once at cold start (module load), not per-invocation — Prompt
    Management adds a network round trip, so we pay that cost once per
    Lambda execution environment rather than on every request.
    """
    prompt_arn = os.environ.get("SYSTEM_PROMPT_ARN")
    if not prompt_arn:
        return _FALLBACK_SYSTEM_PROMPT

    bedrock_agent = boto3.client("bedrock-agent", region_name=AWS_REGION)
    response = bedrock_agent.get_prompt(promptIdentifier=prompt_arn)
    # Assumes a single text variant — Prompt Management supports multiple
    # variants per prompt (e.g. for A/B testing different models), but this
    # project only uses one.
    return response["variants"][0]["templateConfiguration"]["text"]["text"]


SYSTEM_PROMPT = _load_system_prompt()

TOOLS = [
    {
        "name": "lookup_ticket",
        "description": (
            "Look up the current status of an internal support ticket by its ID. "
            "Use this whenever the user asks about a specific ticket's status, "
            "priority, or who it's assigned to."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ticket ID, e.g. 'TCK-1001'.",
                }
            },
            "required": ["ticket_id"],
        },
    }
]


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

def lookup_ticket(ticket_id: str) -> dict:
    """The actual 'action' the agent can take. Pure lookup, no side effects."""
    ticket_id = ticket_id.strip().upper()
    if not ticket_id.startswith("TCK-"):
        ticket_id = f"TCK-{ticket_id}"

    response = tickets_table.get_item(Key={"ticket_id": ticket_id})
    item = response.get("Item")

    if item is None:
        return {"found": False, "ticket_id": ticket_id}

    return {"found": True, **item}


# ---------------------------------------------------------------------------
# Bedrock orchestration (the "agent loop")
# ---------------------------------------------------------------------------

def run_agent(user_message: str) -> str:
    messages = [{"role": "user", "content": [{"text": user_message}]}]

    # First call: let Claude decide whether it needs the tool.
    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages,
        toolConfig={"tools": [{"toolSpec": {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": {"json": t["input_schema"]},
        }} for t in TOOLS]},
        inferenceConfig={"maxTokens": 512, "temperature": 0.2},
    )

    output_message = response["output"]["message"]
    stop_reason = response["stopReason"]

    # If Claude didn't ask for a tool, we already have the final answer.
    if stop_reason != "tool_use":
        return _extract_text(output_message)

    # Claude wants to call a tool. Append its request to the conversation,
    # run the tool, and send the result back for a final answer.
    messages.append(output_message)

    tool_results = []
    for block in output_message["content"]:
        if "toolUse" not in block:
            continue
        tool_use = block["toolUse"]
        if tool_use["name"] == "lookup_ticket":
            result = lookup_ticket(tool_use["input"].get("ticket_id", ""))
        else:
            result = {"error": f"Unknown tool: {tool_use['name']}"}

        tool_results.append({
            "toolResult": {
                "toolUseId": tool_use["toolUseId"],
                "content": [{"json": result}],
            }
        })

    messages.append({"role": "user", "content": tool_results})

    final_response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages,
        toolConfig={"tools": [{"toolSpec": {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": {"json": t["input_schema"]},
        }} for t in TOOLS]},
        inferenceConfig={"maxTokens": 512, "temperature": 0.2},
    )

    return _extract_text(final_response["output"]["message"])


def _extract_text(message: dict) -> str:
    return "".join(block.get("text", "") for block in message["content"]).strip()


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """
    Works with:
      - Lambda Function URL (event['body'] is a JSON string)
      - Direct boto3 invoke (event is already the payload dict)
      - Local testing (see test_local.py)
    """
    try:
        if "body" in event:  # Function URL / API Gateway shape
            body = json.loads(event["body"]) if event["body"] else {}
        else:
            body = event

        user_message = body.get("message", "").strip()
        if not user_message:
            return _response(400, {"error": "Missing 'message' in request body."})

        answer = run_agent(user_message)
        return _response(200, {"answer": answer})

    except Exception as e:  # noqa: BLE001 — top-level handler, want to always return JSON
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: dict):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
