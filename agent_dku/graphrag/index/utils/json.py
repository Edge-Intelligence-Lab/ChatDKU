# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""JSON cleaning and formatting utilities."""


def clean_up_json(json_str: str):
    """Clean up json string."""
    first_brace_index = json_str.find('{')
    if first_brace_index != -1:
        json_str = json_str[first_brace_index:]
        
    # Remove content after the last '}'
    last_brace_index = json_str.rfind('}')
    if last_brace_index != -1:
        json_str = json_str[:last_brace_index + 1]
        
    json_str = (
        json_str.replace("\\n", "")
        .replace("\n", "")
        .replace("\r", "")
        .replace('"[{', "[{")
        .replace('}]"', "}]")
        .replace("\\", "")
        .strip()
    )

    # Remove JSON Markdown Frame
    if json_str.startswith("```json"):
        json_str = json_str[len("```json") :]
    if json_str.endswith("```"):
        json_str = json_str[: len(json_str) - len("```")]

    return json_str
