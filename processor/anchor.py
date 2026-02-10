"""
Core weighted anchor processor.

Takes markdown/text documents and produces layered output with weighted anchors.
Pure mechanical extraction — no LLM calls.

Levels:
  1 (highest): title, H1, first paragraph after headings, bold text
  2 (medium):  H2/H3, list items, definitions (lines with ":" or "—")
  3 (full):    everything else
"""

import re
from dataclasses import dataclass, field


@dataclass
class AnnotatedLine:
    text: str
    level: int  # 1, 2, or 3


def _is_heading(line: str) -> int:
    """Return heading level (1-6) or 0 if not a heading."""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return 0
    match = re.match(r"^(#{1,6})\s", stripped)
    return len(match.group(1)) if match else 0


def _is_list_item(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^[-*+]\s", stripped) or re.match(r"^\d+[.)]\s", stripped))


def _is_definition(line: str) -> bool:
    """Lines containing ':' or '—' that look like definitions."""
    stripped = line.strip()
    if not stripped:
        return False
    # Must have content on both sides of the separator
    if re.search(r"\w\s*[:\u2014]\s+\w", stripped):
        # Exclude lines that are just URLs or code
        if stripped.startswith("http") or stripped.startswith("```"):
            return False
        return True
    return False


def _has_bold(line: str) -> bool:
    return bool(re.search(r"\*\*[^*]+\*\*", line))


def _is_code_fence(line: str) -> bool:
    return line.strip().startswith("```")


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _extract_bold_segments(line: str) -> str:
    """Extract just the bold segments from a line."""
    matches = re.findall(r"\*\*([^*]+)\*\*", line)
    return " | ".join(matches) if matches else line


def process_document(text: str) -> list[AnnotatedLine]:
    """Process a document into annotated lines with weight levels.

    Returns a list of AnnotatedLine objects, each with the original text
    and an assigned priority level (1, 2, or 3).
    """
    lines = text.split("\n")
    result: list[AnnotatedLine] = []
    in_code_block = False
    after_heading = False  # next non-blank paragraph is level 1
    first_line = True

    for i, line in enumerate(lines):
        # Track code blocks
        if _is_code_fence(line):
            in_code_block = not in_code_block
            result.append(AnnotatedLine(line, 3))
            continue

        if in_code_block:
            result.append(AnnotatedLine(line, 3))
            continue

        heading_level = _is_heading(line)

        # Blank lines
        if _is_blank(line):
            result.append(AnnotatedLine(line, 3))
            continue

        # Title / H1 — level 1
        if heading_level == 1 or (first_line and not _is_blank(line) and heading_level == 0):
            result.append(AnnotatedLine(line, 1))
            after_heading = True
            first_line = False
            continue

        first_line = False

        # H2/H3 — level 2
        if heading_level in (2, 3):
            result.append(AnnotatedLine(line, 2))
            after_heading = True
            continue

        # H4+ — level 2 (still structural)
        if heading_level >= 4:
            result.append(AnnotatedLine(line, 2))
            after_heading = True
            continue

        # First paragraph after any heading — level 1 (topic sentence)
        if after_heading and not _is_blank(line):
            result.append(AnnotatedLine(line, 1))
            after_heading = False
            continue

        # Bold text — level 1
        if _has_bold(line):
            result.append(AnnotatedLine(line, 1))
            continue

        # List items — level 2
        if _is_list_item(line):
            result.append(AnnotatedLine(line, 2))
            continue

        # Definitions — level 2
        if _is_definition(line):
            result.append(AnnotatedLine(line, 2))
            continue

        # Everything else — level 3
        result.append(AnnotatedLine(line, 3))

    return result


def annotate_document(text: str) -> str:
    """Return the full document with <!-- anchor:N --> annotations."""
    annotated = process_document(text)
    output_lines = []
    for item in annotated:
        if not _is_blank(item.text):
            output_lines.append(f"<!-- anchor:{item.level} -->{item.text}")
        else:
            output_lines.append(item.text)
    return "\n".join(output_lines)


def extract_level(text: str, max_level: int) -> str:
    """Extract content up to and including the given level.

    max_level=1: level 1 only (highest priority)
    max_level=2: levels 1 + 2
    max_level=3: everything (full document)
    """
    annotated = process_document(text)
    output_lines = []
    prev_was_blank = False

    for item in annotated:
        if item.level <= max_level:
            # Collapse multiple blank lines
            if _is_blank(item.text):
                if not prev_was_blank:
                    output_lines.append("")
                prev_was_blank = True
            else:
                output_lines.append(item.text)
                prev_was_blank = False

    # Strip trailing blank lines
    while output_lines and output_lines[-1] == "":
        output_lines.pop()

    return "\n".join(output_lines)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: chars / 4."""
    return len(text) // 4


def process_full(text: str) -> dict:
    """Process a document and return all levels plus token counts."""
    level1 = extract_level(text, 1)
    level2 = extract_level(text, 2)
    full = extract_level(text, 3)
    annotated = annotate_document(text)

    return {
        "original_tokens": estimate_tokens(text),
        "level1_tokens": estimate_tokens(level1),
        "level2_tokens": estimate_tokens(level2),
        "full_tokens": estimate_tokens(full),
        "level1_content": level1,
        "level2_content": level2,
        "full_content": full,
        "annotated_content": annotated,
    }
