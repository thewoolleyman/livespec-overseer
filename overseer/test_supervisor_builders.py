"""Track builders, pane captures and assertion helpers for the `supervisor` beside-tests.

The companion to `test_supervisor_fakes`, which holds the tmux/tty doubles themselves.
Split from it because the two together crossed the 200-LLOC soft band, which hard-fails
a RELEASE via `check-no-lloc-soft-warnings`.

No tests live here; see `test_supervisor_fakes` for why the `test_` prefix and the
public member names are both load-bearing.
"""

from test_supervisor_capture_builders import (
    HINT as HINT,
)
from test_supervisor_capture_builders import (
    IDLE_BOX as IDLE_BOX,
)
from test_supervisor_capture_builders import (
    RULE as RULE,
)
from test_supervisor_capture_builders import (
    SPINNER as SPINNER,
)
from test_supervisor_capture_builders import (
    busy_capture as busy_capture,
)
from test_supervisor_capture_builders import (
    codex_busy_capture as codex_busy_capture,
)
from test_supervisor_capture_builders import (
    codex_idle_capture as codex_idle_capture,
)
from test_supervisor_capture_builders import (
    idle_capture as idle_capture,
)
from test_supervisor_codex_builders import (
    adopt_codex_ready as adopt_codex_ready,
)
from test_supervisor_codex_builders import (
    adopt_sup as adopt_sup,
)
from test_supervisor_codex_builders import (
    codex_home_with as codex_home_with,
)
from test_supervisor_core_builders import make_supervisor as make_supervisor
from test_supervisor_fakes import FakeTmux as FakeTmux
from test_supervisor_render_builders import (
    GREEN as GREEN,
)
from test_supervisor_render_builders import (
    NUDGE_SENTINEL as NUDGE_SENTINEL,
)
from test_supervisor_render_builders import (
    RESET as RESET,
)
from test_supervisor_render_builders import (
    WRAPUP_SENTINEL as WRAPUP_SENTINEL,
)
from test_supervisor_render_builders import (
    cell_row as cell_row,
)
from test_supervisor_render_builders import (
    nudge_count as nudge_count,
)
from test_supervisor_render_builders import (
    render_of as render_of,
)
from test_supervisor_render_builders import (
    row_line as row_line,
)
from test_supervisor_render_builders import (
    wrapup_count as wrapup_count,
)
from test_supervisor_restart_builders import (
    arm_ready_marker as arm_ready_marker,
)
from test_supervisor_restart_builders import (
    assert_no_tmux_scoping as assert_no_tmux_scoping,
)
from test_supervisor_restart_builders import (
    on_respawn as on_respawn,
)
from test_supervisor_restart_builders import (
    undeletable_state_file as undeletable_state_file,
)
from test_supervisor_restart_builders import (
    unsubmitted_resume_capture as unsubmitted_resume_capture,
)
from test_supervisor_store_builders import (
    TEST_EPIC as TEST_EPIC,
)
from test_supervisor_store_builders import (
    declare as declare,
)
from test_supervisor_store_builders import (
    isolate_store as isolate_store,
)
from test_supervisor_store_builders import (
    key_for as key_for,
)
from test_supervisor_store_builders import (
    make_plan as make_plan,
)
from test_supervisor_store_builders import (
    mapped_track as mapped_track,
)
from test_supervisor_store_builders import (
    write_fresh_supervisor_state as write_fresh_supervisor_state,
)
from test_supervisor_store_builders import (
    write_session as write_session,
)

__all__: list[str] = []
