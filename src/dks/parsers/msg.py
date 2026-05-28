"""MSG parser via extract-msg — Outlook email → TypedContentItem.

Emails are converted to a heading + headers block + one paragraph block per
body paragraph, all under `DocxLocator` (subject as section). Attachments are
not extracted — re-ingest each attachment separately via its own parser.
"""

import contextlib
from pathlib import Path
from typing import Any

import extract_msg

from dks.locators import DocxLocator
from dks.types import TypedContentItem


def parse_msg_file(path: Path) -> list[TypedContentItem]:
    """Parse an Outlook .msg file into typed content items.

    Layout produced:
      - 1 heading item (the subject; falls back to "(no subject)").
      - 1 text item with From / To / Cc / Date headers (if any are present).
      - N text items, one per paragraph of the body (split on blank lines).

    All items live under the same `DocxLocator(section=<subject>)`, so block_ids
    encode as `<source>#§<subject>#p<idx>`.
    """
    # extract-msg's `openMsg` returns subclasses (Message, Appointment, etc.) whose
    # email-specific attributes (date, body, ...) aren't on the static MSGFile base
    # type. Use Any so type-checking doesn't choke on the runtime-only fields.
    msg: Any = extract_msg.openMsg(str(path))
    try:
        items: list[TypedContentItem] = []
        subject = (msg.subject or "(no subject)").strip() or "(no subject)"

        items.append(
            TypedContentItem(
                content=subject,
                block_type="heading",
                locator=DocxLocator(section=subject, paragraph_idx=0),
            )
        )

        header_lines: list[str] = []
        if msg.sender:
            header_lines.append(f"From: {msg.sender}")
        if msg.to:
            header_lines.append(f"To: {msg.to}")
        if msg.cc:
            header_lines.append(f"Cc: {msg.cc}")
        if msg.date:
            header_lines.append(f"Date: {msg.date}")

        paragraph_idx = 1
        if header_lines:
            items.append(
                TypedContentItem(
                    content="\n".join(header_lines),
                    block_type="text",
                    locator=DocxLocator(section=subject, paragraph_idx=paragraph_idx),
                )
            )
            paragraph_idx += 1

        body = (msg.body or "").strip()
        if body:
            for paragraph in body.split("\n\n"):
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                items.append(
                    TypedContentItem(
                        content=paragraph,
                        block_type="text",
                        locator=DocxLocator(section=subject, paragraph_idx=paragraph_idx),
                    )
                )
                paragraph_idx += 1

        return items
    finally:
        # extract-msg keeps a file handle on the underlying OLE file; close it.
        with contextlib.suppress(Exception):
            msg.close()
