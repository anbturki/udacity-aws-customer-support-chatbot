# Customer Support Chatbot with Amazon Bedrock AgentCore

Udacity **Future AWS Agent Engineer** (nd905), project cd14762. Submitted and passed.

A customer support chatbot that routes every message to exactly one of three
behaviours, with all routing logic expressed in a single system prompt:

1. **Bug report** - collect description, steps to reproduce and environment across
   turns, then file the ticket through an AgentCore Gateway tool backed by Lambda
   and DynamoDB, and relay the ticket ID.
2. **Platform question** - answer only from the embedded FAQ.
3. **Anything else** - hand off to the human support line.

## Layout

| Path | What it is |
|---|---|
| `system_prompt.txt` | the deliverable: routing, procedures and absolute rules |
| `create_bug_report.py` | Lambda handler, with validation extended to reject placeholder values |
| `cloudformation-tool.yaml` | tool stack: Lambda, DynamoDB, Gateway target |
| `cloudformation-testing.yaml` | testing stack |
| `create_harness.py` | AgentCore harness creation, cross-session memory disabled |
| `setup_gateway.py` | Gateway and tool schema |
| `chat.py` | interactive client |
| `generate-eval-dataset.py` | builds the Bedrock Evaluations dataset |
| `harness-tests.json`, `flow-tests.json` | 15 test cases |

## Result

Bedrock Evaluations correctness **1.000 across all 15 records**.

## Notes

This repository holds the source only. Test transcripts, console screenshots and
evaluation output were part of the Udacity submission and are not published here.

All AWS resources were destroyed after submission.
