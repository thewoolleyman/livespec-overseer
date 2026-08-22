"""Deterministic token-free render for a foreman evidence document."""

from __future__ import annotations

import jsonio

__all__: list[str] = ["render_document"]


def source_line(*, document: dict[str, object]) -> str:
    sources = jsonio.as_object(value=document.get("sources")) or {}
    snapshot = jsonio.as_object(value=sources.get("snapshot")) or {}
    attention = jsonio.as_object(value=sources.get("needs_attention")) or {}
    journal = jsonio.as_object(value=sources.get("dispatch_journal")) or {}
    release_lane = jsonio.as_object(value=sources.get("release_lane"))
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
    line = (
        f"sources: {' '.join(snapshot_bits)}; "
        f"{' '.join(attention_bits)}; {' '.join(journal_bits)}"
    )
    if release_lane is not None:
        release_bits = [
            f"release_lane={release_lane.get('status')}",
            str(release_lane.get("workflow")),
        ]
        if isinstance(release_lane.get("reason"), str):
            release_bits.append(str(release_lane["reason"]))
        line = f"{line}; {' '.join(release_bits)}"
    return line


def row_line(*, row: dict[str, object]) -> str:
    note = row.get("note")
    note_text = str(note) if isinstance(note, str) and note else "-"
    human_wait = "yes" if row.get("human_wait") is True else "no"
    line = (
        f"  {row.get('topic')} | {row.get('status')} | "
        f"ctx={row.get('ctx')} | human_wait={human_wait}"
    )
    supervisor_handoff = row.get("supervisor_handoff")
    if isinstance(supervisor_handoff, str):
        line = f"{line} | supervisor={supervisor_handoff}"
    evidence = evidence_text(row=row)
    if evidence:
        line = f"{line} | {evidence}"
    premises = premises_text(row=row)
    if premises:
        line = f"{line} | {premises}"
    skips = premise_skips_text(row=row)
    if skips:
        line = f"{line} | {skips}"
    return f"{line} | {note_text}"


def evidence_text(*, row: dict[str, object]) -> str:
    keys = (
        "picker_open",
        "stall_seconds",
        "supervisor_state_age",
        "proposed_changes_count",
        "pane_content_hash",
    )
    if not any(key in row for key in keys):
        return ""
    picker_open = "yes" if row.get("picker_open") is True else "no"
    pane_hash = row.get("pane_content_hash")
    pane_hash_text = pane_hash[:12] if isinstance(pane_hash, str) else None
    return (
        f"picker_open={picker_open} | stall_seconds={row.get('stall_seconds')} | "
        f"supervisor_state_age={row.get('supervisor_state_age')} | "
        f"proposed_changes={row.get('proposed_changes_count')} | "
        f"pane_hash={pane_hash_text}"
    )


def premises_text(*, row: dict[str, object]) -> str:
    raw_premises = jsonio.as_list(value=row.get("wait_premises")) or []
    rendered = [
        premise_fragment(premise=premise)
        for premise in (jsonio.as_object(value=raw) for raw in raw_premises)
        if premise is not None
    ]
    return f"premises={', '.join(rendered)}" if rendered else ""


def premise_skips_text(*, row: dict[str, object]) -> str:
    raw_skips = jsonio.as_list(value=row.get("wait_premise_skips")) or []
    rendered = [
        str(skip.get("reason"))
        for skip in (jsonio.as_object(value=raw) for raw in raw_skips)
        if skip is not None
    ]
    return f"premise_skips={', '.join(rendered)}" if rendered else ""


def premise_fragment(*, premise: dict[str, object]) -> str:
    kind = premise.get("kind")
    target_id = premise.get("target_id")
    recheck_by = premise.get("recheck_by")
    return f"{kind}:{target_id} recheck_by={recheck_by}"


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
    items = items_from_attention(attention=document.get("needs_attention"))
    needs_you = uses_needs_you(rows=rows, items=items)
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
    lines.extend(["", "NEEDS YOU:" if needs_you else "needs attention:"])
    line = attention_line if needs_you else legacy_attention_line
    lines.extend(line(item=item) for item in items)
    if not items:
        lines.append("  none")
    lines.extend(["", "dispatch journal:"])
    lines.extend(f"  {record.get('action')}" for record in journal)
    if not journal:
        lines.append("  none")
    return "\n".join(lines) + "\n"


def attention_line(*, item: dict[str, object]) -> str:
    session = item.get("session_name") or item.get("tmux") or item.get("id")
    return f"  {item.get('id')} | {session} | {item.get('kind')} | {item.get('title')}"


def legacy_attention_line(*, item: dict[str, object]) -> str:
    return f"  {item.get('id')} | {item.get('kind')} | {item.get('title')}"


def uses_needs_you(*, rows: list[dict[str, object]], items: list[dict[str, object]]) -> bool:
    return any(row.get("tmux") for row in rows) or any(
        item.get("session_name") or item.get("tmux") for item in items
    )
