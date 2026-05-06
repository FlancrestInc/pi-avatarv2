import json
import re


class ParseError(ValueError):
    pass


def parse_value(content, parser_config):
    if parser_config.type == "raw":
        value = content
    elif parser_config.type == "json_path":
        value = _json_path(content, parser_config.path)
    elif parser_config.type == "regex":
        value = _regex(content, parser_config.pattern, parser_config.group)
    else:
        raise ParseError(f"Unsupported parser type: {parser_config.type}")

    return _cast(value, parser_config.cast)


def _json_path(content, path):
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON: {exc}") from exc

    parts = _json_path_parts(path)
    for part in parts:
        if isinstance(value, dict):
            if part not in value:
                raise ParseError(f"JSON path missing key: {part}")
            value = value[part]
        elif isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError) as exc:
                raise ParseError(f"JSON path missing index: {part}") from exc
        else:
            raise ParseError(f"JSON path cannot descend into {type(value).__name__}")
    return value


def _json_path_parts(path):
    if not path or path == "$":
        return []
    if not path.startswith("$."):
        raise ParseError("JSON path must start with $.")
    return [part for part in path[2:].split(".") if part]


def _regex(content, pattern, group):
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        raise ParseError("Regex did not match source content")

    try:
        if isinstance(group, str) and group.isdigit():
            group = int(group)
        return match.group(group)
    except IndexError as exc:
        raise ParseError(f"Regex group not found: {group}") from exc


def _cast(value, cast):
    if cast == "string":
        return "" if value is None else str(value)
    if cast == "number":
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ParseError(f"Value is not numeric: {value}") from exc
    if cast == "bool":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
        raise ParseError(f"Value is not boolean: {value}")
    raise ParseError(f"Unsupported cast: {cast}")
