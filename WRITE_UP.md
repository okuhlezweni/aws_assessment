## Design Decisions

**Model Choice:** Claude Haiku 4.5 was chosen for this assessment. The model is relatively cheap but still fast. Since this is a ticket lookup assistant which mostly deals with short questions and generates short, exact-match retrieval answers, an expensive and compute-heavy model would've been too much for what the task actually requires. 
\\
**How the agent calls the tool:** There is an instruction in the system prompt to use lookup_ticket, the action which allows it to look for the ticket in the dataset of tickets, whenever a ticket ID is given.

**Trade-offs**
- **DynamoDB vs JSON file:** I initially started with a JSON file for the mock ticket data, but since I wanted more hands-on exposure to AWS services, I opted to use a DynamoDB table that the Lambda function calls instead. This also helped with gaining practice on setting up the necessary IAM role permissions.

## What I learned
I was able to use this assessment to put what I learned in the AWS courses and the Cloud Practitioner exam to practice. I was exposed to new AWS services and tools within services that I wasn't familiar with before, such as Bedrock Converse API to manage the conversations with the assistant and Bedrock Prompt Management to manage and store the system prompt. It was also interesting to see the differences between Microsoft Azure and AWS, and how each cloud platform differs in the approach to creating the same solution. Having built a similar tool-calling platform in Azure, it was interesting to see where the concepts map directly (for example the system prompt, tool schema, the model deciding when to call a tool) and where the concepts differ (Azure OpenAI requires a model deployment resource before you can call it, while Bedrock enables model access at the account level with no need for a deployment step). 

\\
## Limitations
**Bedrock Guardrails:** Currently, the system prompt is the only function which filters undesirable content and protects against model hallucination. I would implement Bedrock Guardrails to add further protection against this. 

\\
## Cost and Security

**Cost:**
- **Claude Haiku 4.5:** charged per input/output token. A handful of test
  conversations during development totals a small fraction of a cent to a few
  cents overall.
- **Lambda:** Free Tier covers 1M requests and 400,000 GB-seconds of compute per month —
  nowhere close to being used here.
- **DynamoDB:** on-demand billing mode, 20 items, well within Free Tier limits.
- **Function URL:** no additional charge beyond the underlying Lambda invocation.


**Security:**
- No AWS access keys or secrets are hardcoded anywhere in the repository. The Lambda
  uses its IAM execution role to call Bedrock and DynamoDB; local testing uses
  credentials from `aws configure`, stored outside the project folder in
  `~/.aws/credentials` and covered by `.gitignore`.
- I created a dedicated IAM user for this project rather than using the AWS account's
  root credentials for day-to-day work — root is reserved for account-level actions only.
- The Lambda's IAM role is scoped to only the permissions it actually needs:
  `bedrock:Converse`, `bedrock:GetPrompt`, and `dynamodb:GetItem` on the specific
  `Tickets` table, rather than broad access. (I did use a broader `AdministratorAccess`
  policy on my own IAM user while building, to move faster without hitting permission
  walls mid-development — a reasonable trade-off for a time-boxed exercise, though I'd
  scope that down too for anything longer-lived.)
- **Known gap:** the Function URL's auth type is `NONE`, and CORS is set to allow any
  origin (`*`). This is acceptable for a throwaway demo backed entirely by mock data, but
  it means anyone with the URL could call the assistant and incur Bedrock costs on my
  account. For a real deployment, I'd switch to `AWS_IAM` auth (requiring signed
  requests) or put an authenticated API Gateway in front, and restrict CORS to the
  specific domain hosting the front-end.