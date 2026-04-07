"""Pure-function XML and token-based tool-call parsers."""

import re
import json
from typing import Any, Dict, List, Optional, Tuple

from .utils import generate_short_id, sanitize_tool_name


def parse_xml_tool_calls(
    content: str, known_function_names: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Parse XML-formatted and token-based tool calls embedded in message content.

    Handles several distinct formats:
    1. Standard <invoke>
    2. DeepSeek <functioninvoke>
    3. Token-based (to=functions.NAME)
    4. Call-prefix tags (<call:NAME>)
    5. Named tags (<FUNCTION_NAME>) — only if in known_function_names.
    """
    tool_calls = []
    seen_segments = set()  # prevent double-parsing the same content

    def add_call(name: str, args: str, segment: str):
        if segment in seen_segments:
            return
        seen_segments.add(segment)
        tool_calls.append(
            {
                "id": f"call_via_content_{generate_short_id()}",
                "type": "function",
                "function": {"name": sanitize_tool_name(name), "arguments": args},
            }
        )

    # 1. <invoke> tags
    invoke_matches = re.finditer(r"<invoke([^>]*)>(.*?)</invoke>", content, re.DOTALL)
    for match in invoke_matches:
        attrs = match.group(1).strip()
        args_str = match.group(2).strip()
        name_match = re.search(r'name=["\']([^"\']+)["\']', attrs)
        fn_name = name_match.group(1) if name_match else "error_missing_function_name"
        if args_str.startswith("<![CDATA[") and args_str.endswith("]]>"):
            args_str = args_str[9:-3].strip()
        add_call(fn_name, args_str, match.group(0))

    # 2. DeepSeek <functioninvoke>
    function_invoke_matches = re.finditer(
        r"<functioninvoke([^>]*)>(.*?)</(?:parameterinvoke|functioninvoke|invoke)>",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    for match in function_invoke_matches:
        attrs = match.group(1).strip()
        inner = match.group(2).strip()
        name_match = re.search(r'name=["\']([^"\']+)["\']', attrs)
        fn_name = name_match.group(1) if name_match else "error_missing_function_name"
        args: Dict[str, Any] = {}
        param_matches = re.finditer(
            r'<parameter\s+name=["\']([^"\']+)["\'][^>]*>(.*?)(?:</parameter>|$)',
            inner,
            re.DOTALL | re.IGNORECASE,
        )
        for p_match in param_matches:
            args[p_match.group(1)] = p_match.group(2).strip()
        args_str = json.dumps(args) if args else inner
        add_call(fn_name, args_str, match.group(0))

    # 3. Token-based (to=functions.NAME json<|message|>ARGS)
    token_matches = re.finditer(
        r"to=functions\.([a-zA-Z0-9_<|>-]+).*?<\|message\|>(.*?)(?=<\||\n\s*\n|$)",
        content,
        re.DOTALL,
    )
    for match in token_matches:
        add_call(match.group(1), match.group(2).strip(), match.group(0))

    # 4. Call-prefix tags (<call:NAME>ARGS</call:NAME>)
    call_prefix_matches = re.finditer(
        r"<call:([a-zA-Z0-9_-]+)>(.*?)</call:\1>", content, re.DOTALL
    )
    for match in call_prefix_matches:
        add_call(match.group(1), match.group(2).strip(), match.group(0))

    # 5. Named tags (<FUNCTION_NAME>) — if known
    if known_function_names:
        for name in known_function_names:
            tag_matches = re.finditer(
                f"<{name}([^>]*)>(.*?)</{name}>", content, re.DOTALL
            )
            for match in tag_matches:
                add_call(name, match.group(2).strip(), match.group(0))

    return tool_calls


def sanitize_tool_id(tool_id: Optional[str]) -> str:
    """Ensure tool ID matches OpenAI regex: ^[a-zA-Z0-9_-]+$."""
    if not tool_id:
        return f"call_{generate_short_id()}"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", tool_id)


def extract_and_sanitize_tool_calls(
    message_tool_calls: Optional[List[Any]],
    content: Optional[str],
    known_function_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Collect native & XML tool calls, sanitize IDs, and ensure names."""
    calls = []
    if message_tool_calls:
        # Handle both list of objects (OpenAI MessageToolCall) and list of dicts
        for tc in message_tool_calls:
            if hasattr(tc, "model_dump"):
                calls.append(tc.model_dump())
            elif isinstance(tc, dict):
                calls.append(tc.copy())
            else:
                # Fallback for older Pydantic or unknown objects
                calls.append(vars(tc))

    if content:
        calls.extend(parse_xml_tool_calls(content, known_function_names))

    for tc in calls:
        tc["id"] = sanitize_tool_id(tc.get("id"))
        if not tc.get("function"):
            tc["function"] = {"name": "unknown_function", "arguments": "{}"}
        tc["function"]["name"] = sanitize_tool_name(tc["function"].get("name"))

    return calls


def extract_reasoning(message: Any) -> Tuple[Optional[str], Optional[str]]:
    """Extract chain-of-thought reasoning and Google thought_signature."""
    current_reasoning = getattr(message, "reasoning", None)
    thought_signature = None

    extra_fields = getattr(message, "model_extra", None) or getattr(
        message, "extra_content", None
    )
    if extra_fields:
        extra_content = (
            extra_fields.get("extra_content", extra_fields)
            if isinstance(extra_fields, dict)
            else extra_fields
        )

        if not current_reasoning and isinstance(extra_fields, dict):
            current_reasoning = extra_fields.get("reasoning")

        if isinstance(extra_content, dict):
            google_data = extra_content.get("google")
            if isinstance(google_data, dict):
                thought_signature = google_data.get("thought_signature")

    return current_reasoning, thought_signature
