"""Deterministic token-free render for a foreman evidence document."""

from __future__ import annotations

import jsonio

__all__: list[str] = ["render_document"]


def source_line(*, document: dict[str, object]) -> str:
    sources = jsonio.as_object(value=document.get("sources")) or {}
    snapshot = jsonio.as_object(value=sources.get("snapshot")) or {}
    attention = jsonio.as_object(value=sources.get("needs_attention")) or {}
    journal = jsonio.as_object(value=sources.get("dispatch_journal")) or {}
    snapshot_bits = [
        f"snapshot={snapshot.get('status')}",
        str(snapshot.get("mode")),
        f"rows={snapshot.get('rows_used')}",
    ]
    attention_bits = [f"needs_attention={attention.get('status')}"]
    if isinstance(attention.get("reason"), str):
        attention_bits.append(str(attention["reason"]))
    journal_bits = [
        f"dispatch_journal={journal.get('status')}",
        f"records={journal.get('records_read')}",
    ]
    return (
        f"sources: {' '.join(snapshot_bits)}; "
        f"{' '.join(attention_bits)}; {' '.join(journal_bits)}"
    )


def row_line(*, row: dict[str, object]) -> str:
    note = row.get("note")
    note_text = str(note) if isinstance(note, str) and note else "-"
    human_wait = "yes" if row.get("human_wait") is True else "no"
    return (
        f"  {row.get('topic')} | {row.get('status')} | "
        f"ctx={row.get('ctx')} | human_wait={human_wait} | {note_text}"
    )


def items_from_attention(*, attention: object) -> list[dict[str, object]]:
    obj = jsonio.as_object(value=attention)
    if obj is None:
        return []
    raw_items = jsonio.as_list(value=obj.get("items"))
    if raw_items is None:
        return []
    return [item for item in (jsonio.as_object(value=raw) for raw in raw_items) if item is not None]


def object_rows(*, value: object) -> list[dict[str, object]]:
    raw_rows = jsonio.as_list(value=value) or []
    return [row for row in (jsonio.as_object(value=raw) for raw in raw_rows) if row is not None]


def render_document(*, document: dict[str, object]) -> str:
    snapshot = jsonio.as_object(value=document.get("snapshot")) or {}
    rows = object_rows(value=snapshot.get("rows"))
    journal = object_rows(value=document.get("dispatch_journal"))
    lines = [
        f"foreman-gather {document.get('generated_at')}",
        f"repo: {document.get('repo')}",
        source_line(document=document),
        "",
        "snapshot rows:",
    ]
    lines.extend(row_line(row=row) for row in rows)
    if not rows:
        lines.append("  none")
    lines.extend(["", "needs attention:"])
    items = items_from_attention(attention=document.get("needs_attention"))
    lines.extend(f"  {item.get('id')} | {item.get('kind')} | {item.get('title')}" for item in items)
    if not items:
        lines.append("  none")
    lines.extend(["", "dispatch journal:"])
    lines.extend(f"  {record.get('action')}" for record in journal)
    if not journal:
        lines.append("  none")
    return "\n".join(lines) + "\n"
