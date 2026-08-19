# Internal Helpdesk Assistant

A simple AI agent built on **Amazon Bedrock (Claude Haiku 4.5)** and **AWS Lambda**
that answers general workplace questions and looks up support ticket status
via a tool call with aweb front-end on top.

## What it does

- User asks a question (via the web UI, CLI, or a direct HTTP call).
- Claude (via Bedrock's `converse` API) decides: answer directly, or call the
  `lookup_ticket` tool if the question is about a specific ticket ID.
- If the tool is called, the Lambda function looks the ticket up in DynamoDB
  and sends the result back to Claude, which turns it into a natural-language
  answer.
- The Lambda's system prompt is fetched from **Bedrock Prompt Management**
  rather than hardcoded, with a local fallback for offline testing.

## AWS services used

| Service | Role |
|---|---|
| Amazon Bedrock (Converse API) | Foundation model (Claude Haiku 4.5) — reasoning + tool-use decisions |
| Amazon Bedrock Prompt Management | Stores and versions the system prompt |
| AWS Lambda | Runs the orchestration loop and the tool logic (`lookup_ticket`) |
| Amazon DynamoDB | Ticket data store (table: `Tickets`, partition key: `ticket_id`) |
| Lambda Function URL | HTTP entry point |
| IAM | Execution role scoped to `bedrock:Converse`, `bedrock:GetPrompt`, `dynamodb:GetItem` |


A static HTML/JS front-end calls the Function URL directly from the browser
(no separate hosting service required — it's a single file).

## Setup & deployment

### 1. Create the DynamoDB table

Create the DynamoDB table 'Tickets' in the AWS Management Console, set the partition key as 'ticket_id', then load the tickets into the console locally


### 2. Create the system prompt in Bedrock Prompt Management

Create the system prompt in Bedrock Prompt Management, ad create a version of it. Copy the prompt ARN.

### 3. Create the IAM role for Lambda

Attach the AWS-managed `AWSLambdaBasicExecutionRole`, plus this inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:Converse"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "bedrock:GetPrompt",
      "Resource": "arn:aws:bedrock:*:*:prompt/*"
    },
    {
      "Effect": "Allow",
      "Action": "dynamodb:GetItem",
      "Resource": "arn:aws:dynamodb:*:*:table/Tickets"
    }
  ]
}
```

### 4. Create the Lambda function

Attach the role from step 4, then paste `lambda_function.py` into the inline code
editor and click **Deploy**.

Put the system prompt ARN into the environment variables as SYSTEM_PROMPT_ARN


### 5. Add a Function URL
- Auth type: `NONE` (fine
for a demo; see the security note in WRITEUP.md for why this isn't
appropriate beyond a demo). Enable **CORS** here too and Allow origin `*`,
- Allow methods `POST`, Allow headers `content-type` as this is required for
the browser front-end to be able to call it.

### 6. Test it

After clicking deploy, add a test event to test whether the lambda function works. 



