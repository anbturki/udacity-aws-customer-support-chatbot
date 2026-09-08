"""Lambda function behind the AgentCore Gateway `create_bug_report` tool.

This file mirrors the code embedded in cloudformation-tool.yaml — if you
change one, keep the other in sync.

How the gateway calls this function:

* The **tool arguments** arrive directly as the Lambda ``event`` — a plain
  JSON object such as::

      {"description": "...", "stepsToReproduce": "...", "environment": "..."}

  (Bedrock Agents Classic used to wrap arguments in a ``messageVersion`` /
  ``parameters`` envelope; the gateway does not.)

* The **tool name** arrives via the Lambda client context:
  ``context.client_context.custom["bedrockAgentCoreToolName"]``, namespaced
  as ``<targetName>___<toolName>`` (three underscores).

* Whatever the handler **returns** is passed back to the model as the tool
  result.

Tip: the ``print("EVENT:", ...)`` below writes the raw event to CloudWatch
Logs (log group ``/aws/lambda/<function-name>``). Check it after your first
test invoke to see the real event shape.
"""

import json
import re
import os
import uuid
from datetime import datetime, timezone
import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

PLACEHOLDER_VALUES = frozenset({
    "unknown", "n/a", "na", "none", "null", "nil", "tbd", "unspecified",
    "not provided", "not specified", "not available", "not sure",
    "not applicable", "unavailable", "customer did not know", "did not know",
    "no steps", "no steps provided", "no", "-", "--", "?", ".",
})


_ASKING = re.compile(
    r"^(please\s|could you\s|can you\s|kindly\s|provide\s|specify\s|tell me\b)",
    re.IGNORECASE)
_NARRATED = re.compile(
    r"^(the\s+)?(user|customer)\s+"
    r"(is|was|has|had|did|does|says|said|reports|reported|mentions|"
    r"mentioned|states|stated|indicates|indicated|wants|needs|tried|"
    r"experienced)\b",
    re.IGNORECASE)


def _is_placeholder(value):
    """True when the model filled a required field with a filler token rather
    than something the customer actually said."""
    # HTML entities and tags are stripped first: the model used "&nbsp;"
    # to slip an empty value past this check.
    normalized = re.sub(r"&[a-z]+;|&#\d+;", " ", value, flags=re.IGNORECASE)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip().strip(".!?-_/ ").casefold()
    # Stripping punctuation can empty the value entirely, which is how a lone
    # "." got past this check and into a ticket.
    if len(normalized) < 3:
        return True
    # Prefix rather than exact match, so "Not provided yet" is caught.
    return any(normalized == p or normalized.startswith(p + " ")
               for p in PLACEHOLDER_VALUES)


def _is_not_an_answer(value):
    """True when the model put its own question or narration in the field
    instead of what the customer said."""
    v = value.strip()
    return bool(_ASKING.match(v)) or bool(_NARRATED.match(v)) or v.endswith("?")


def _tool_name(context):
    """AgentCore Gateway passes the tool name via the Lambda client
    context, namespaced as "<targetName>___<toolName>"."""
    client_context = getattr(context, "client_context", None)
    custom = getattr(client_context, "custom", None) or {}
    name = custom.get("bedrockAgentCoreToolName", "")
    return name.split("___")[-1] if "___" in name else name


def lambda_handler(event, context):
    # The gateway sends the tool arguments directly as the event.
    # Keep this print: it shows the exact event shape in CloudWatch
    # Logs, which is invaluable when debugging your first invoke.
    print("EVENT:", json.dumps(event, default=str))

    tool_name = _tool_name(context)
    print("TOOL NAME:", tool_name)
    if tool_name and tool_name != "create_bug_report":
        return {"error": f"unsupported tool: {tool_name}"}

    if not isinstance(event, dict):
        return {"error": "unexpected event shape", "event": str(event)}

    description = str(event.get("description") or "").strip()
    steps = str(event.get("stepsToReproduce") or "").strip()
    environment = str(event.get("environment") or "").strip()

    # All three fields are required and must be non-empty. The model
    # sometimes tries to satisfy a "required" parameter with an empty
    # string — returning an error here tells it to go back and ask the
    # customer instead of filing an incomplete ticket.
    fields = [("description", description),
              ("stepsToReproduce", steps),
              ("environment", environment)]

    missing = [name for name, value in fields if not value]
    if missing:
        return {"error": "missing required field: " + missing[0]
                         + ". In your next reply ask the customer for " + missing[0]
                         + " and nothing else, then call this tool again."}

    # The model also tries to get past a required field by filling it with
    # "Unknown" or "Not provided" instead of asking. Reject those too, so an
    # incomplete ticket can never reach the table.
    rejected = [name for name, value in fields
                if _is_placeholder(value) or _is_not_an_answer(value)]
    if rejected:
        # Name only the first field. Listing them all makes the model ask the
        # customer several questions in one reply.
        first = rejected[0]
        return {"error": "the value for " + first + " was not accepted. It must be "
                         "what the customer actually told you, not a placeholder, "
                         "not your own question, and not a guess. In your next "
                         "reply ask the customer for " + first + " and nothing "
                         "else, then call this tool again once they answer."}

    ticket_id = str(uuid.uuid4())
    item = {
        "ticketId": ticket_id,
        "description": description,
        "stepsToReproduce": steps,
        "environment": environment,
        "status": "OPEN",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    table.put_item(Item=item)

    # Whatever this returns is handed back to the model as the
    # tool result.
    return {"ticketId": ticket_id, "status": "OPEN"}
