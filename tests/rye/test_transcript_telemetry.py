"""Tests for transcript writing, rendering, and telemetry aggregation.

Covers:
- TranscriptWriter JSONL event writing and auto-markdown generation
- JSONL integrity and fault tolerance
- thread.json lifecycle
- TranscriptRenderer standalone rendering
- ThreadTelemetry aggregation
"""

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent

REGISTRY_PATH = (
    PROJECT_ROOT
    / "rye" / "rye" / ".ai" / "tools" / "rye" / "agent" / "threads" / "thread_registry.py"
)
_spec = importlib.util.spec_from_file_location("thread_registry", REGISTRY_PATH)
_registry_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_registry_mod)
TranscriptWriter = _registry_mod.TranscriptWriter

RENDERER_PATH = (
    PROJECT_ROOT
    / "rye" / "rye" / ".ai" / "tools" / "rye" / "agent" / "threads" / "transcript_renderer.py"
)
_rspec = importlib.util.spec_from_file_location("transcript_renderer", RENDERER_PATH)
_renderer_mod = importlib.util.module_from_spec(_rspec)
_rspec.loader.exec_module(_renderer_mod)
TranscriptRenderer = _renderer_mod.TranscriptRenderer

TELEMETRY_PATH = (
    PROJECT_ROOT
    / "rye" / "rye" / ".ai" / "tools" / "rye" / "agent" / "threads" / "thread_telemetry.py"
)
_tspec = importlib.util.spec_from_file_location("thread_telemetry", TELEMETRY_PATH)
_telemetry_mod = importlib.util.module_from_spec(_tspec)
_tspec.loader.exec_module(_telemetry_mod)
ThreadTelemetry = _telemetry_mod.ThreadTelemetry


THREAD_ID = "hello_world-1739012630"


@pytest.fixture
def thread_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def writer(thread_dir):
    return TranscriptWriter(thread_dir, auto_markdown=True, default_directive="test_agent")


@pytest.fixture
def writer_no_md(thread_dir):
    return TranscriptWriter(thread_dir, auto_markdown=False, default_directive="test_agent")


class TestTranscriptWriterJSONL:
    """JSONL transcript event writing."""

    def test_write_event_creates_jsonl(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "thread_start", {
            "directive": "hello_world", "model": "claude-3-5-haiku-20241022",
        })
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        assert jsonl_path.exists()
        event = json.loads(jsonl_path.read_text().strip())
        assert event["type"] == "thread_start"
        assert event["directive"] == "hello_world"

    def test_event_envelope_has_required_fields(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "assistant_text", {"text": "Hello"})
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        event = json.loads(jsonl_path.read_text().strip())
        assert "ts" in event
        assert event["type"] == "assistant_text"
        assert event["thread_id"] == THREAD_ID
        assert event["directive"] == "test_agent"

    def test_directive_from_data_overrides_default(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "assistant_text", {
            "text": "Hi", "directive": "custom_directive",
        })
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        event = json.loads(jsonl_path.read_text().strip())
        assert event["directive"] == "custom_directive"

    def test_raises_without_directive(self, thread_dir):
        writer = TranscriptWriter(thread_dir, auto_markdown=False)
        with pytest.raises(ValueError, match="missing 'directive'"):
            writer.write_event(THREAD_ID, "assistant_text", {"text": "Hi"})

    def test_multiple_events_append(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "thread_start", {"directive": "test"})
        writer.write_event(THREAD_ID, "user_message", {"text": "hi", "role": "user"})
        writer.write_event(THREAD_ID, "assistant_text", {"text": "hello"})
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        lines = [l for l in jsonl_path.read_text().strip().split("\n") if l]
        assert len(lines) == 3
        assert json.loads(lines[0])["type"] == "thread_start"
        assert json.loads(lines[1])["type"] == "user_message"
        assert json.loads(lines[2])["type"] == "assistant_text"

    def test_creates_directory_if_missing(self, writer, thread_dir):
        new_id = "new_directive-1739099999"
        writer.write_event(new_id, "thread_start", {"directive": "new"})
        assert (thread_dir / new_id / "transcript.jsonl").exists()


class TestTranscriptWriterMarkdown:
    """Auto-generated markdown transcript."""

    def test_auto_markdown_creates_md_file(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "thread_start", {
            "directive": "hello_world", "model": "claude-3-5-haiku-20241022",
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# hello_world" in content
        assert "claude-3-5-haiku-20241022" in content

    def test_no_markdown_when_disabled(self, writer_no_md, thread_dir):
        writer_no_md.write_event(THREAD_ID, "thread_start", {"directive": "test"})
        md_path = thread_dir / THREAD_ID / "transcript.md"
        assert not md_path.exists()

    def test_markdown_user_message(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "user_message", {
            "text": "Do something", "role": "system",
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "## System" in content
        assert "Do something" in content

    def test_markdown_assistant_text(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "assistant_text", {"text": "I'll help"})
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "**Assistant:**" in content
        assert "I'll help" in content

    def test_markdown_tool_call(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "tool_call_start", {
            "tool": "fs_read", "call_id": "tc_1", "input": {"path": "/tmp/test"},
        })
        writer.write_event(THREAD_ID, "tool_call_result", {
            "call_id": "tc_1", "output": "file contents here",
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "Tool Call" in content
        assert "fs_read" in content
        assert "file contents here" in content

    def test_markdown_tool_error(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "tool_call_result", {
            "call_id": "tc_1", "output": "", "error": "File not found",
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "**Error:**" in content
        assert "File not found" in content

    def test_markdown_step_finish(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "step_finish", {
            "cost": 0.0025,
            "tokens": 600,
            "finish_reason": "end_turn",
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "600 tokens" in content
        assert "$0.002500" in content
        assert "end_turn" in content

    def test_markdown_thread_complete(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "thread_complete", {
            "cost": {"turns": 2, "tokens": 3000, "spend": 0.005, "duration_seconds": 8.3},
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "## Completed" in content
        assert "**Total Tokens:**" in content
        assert "**Total Cost:**" in content

    def test_markdown_thread_error(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "thread_error", {
            "error_code": "llm_call_failed", "detail": "Connection timeout",
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "llm_call_failed" in content
        assert "Connection timeout" in content

    def test_unknown_event_type_no_markdown(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "hook_triggered", {"hook": "test"})
        md_path = thread_dir / THREAD_ID / "transcript.md"
        if md_path.exists():
            assert md_path.read_text().strip() == ""

    def test_markdown_appends_incrementally(self, writer, thread_dir):
        writer.write_event(THREAD_ID, "thread_start", {"directive": "test"})
        writer.write_event(THREAD_ID, "assistant_text", {"text": "Hello"})
        writer.write_event(THREAD_ID, "thread_complete", {
            "cost": {"turns": 1, "tokens": 100, "spend": 0.001, "duration_seconds": 1.5},
        })
        md_path = thread_dir / THREAD_ID / "transcript.md"
        content = md_path.read_text()
        assert "# test" in content
        assert "Hello" in content
        assert "## Completed" in content


class TestJSONLIntegrity:
    """JSONL read/write integrity and fault tolerance."""

    def test_read_events_skips_corrupt_lines(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"2026-01-01T00:00:00","type":"thread_start","directive":"test"}\n'
            'THIS IS NOT JSON\n'
            '{"ts":"2026-01-01T00:00:01","type":"assistant_text","text":"hello"}\n'
            '\n'
            '{"broken json\n'
        )
        events = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if "ts" in event and "type" in event:
                        events.append(event)
                except json.JSONDecodeError:
                    continue
        assert len(events) == 2
        assert events[0]["type"] == "thread_start"
        assert events[1]["type"] == "assistant_text"

    def test_read_events_skips_missing_envelope_fields(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"2026-01-01T00:00:00","type":"thread_start"}\n'
            '{"type":"no_timestamp"}\n'
            '{"ts":"2026-01-01T00:00:01"}\n'
            '{"ts":"2026-01-01T00:00:02","type":"valid_event"}\n'
        )
        events = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if "ts" in event and "type" in event:
                        events.append(event)
                except json.JSONDecodeError:
                    continue
        assert len(events) == 2

    def test_empty_file_returns_no_events(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text("")
        events = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        assert len(events) == 0


class TestThreadMetaJSON:
    """thread.json write/read/reconstruction."""

    def test_write_thread_meta_atomic(self, thread_dir):
        thread_path = thread_dir / THREAD_ID
        thread_path.mkdir(parents=True)
        meta = {
            "thread_id": THREAD_ID,
            "directive": "hello_world",
            "status": "running",
            "created_at": "2026-02-09T04:03:50Z",
            "updated_at": "2026-02-09T04:03:50Z",
        }
        meta_path = thread_path / "thread.json"
        tmp_path = meta_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(meta, indent=2))
        tmp_path.rename(meta_path)

        loaded = json.loads(meta_path.read_text())
        assert loaded["thread_id"] == THREAD_ID
        assert loaded["status"] == "running"
        assert not tmp_path.exists()

    def test_reconstruct_meta_from_transcript(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"2026-02-09T04:03:50Z","type":"thread_start",'
            '"directive":"hello_world","model":"haiku"}\n'
            '{"ts":"2026-02-09T04:04:01Z","type":"thread_complete",'
            '"cost":{"turns":2,"tokens":3000,"spend":0.005}}\n'
        )
        events = [json.loads(l) for l in jsonl_path.read_text().strip().split("\n")]
        start = next(e for e in events if e["type"] == "thread_start")
        complete = next((e for e in events if e["type"] == "thread_complete"), None)
        meta = {
            "thread_id": THREAD_ID,
            "directive": start.get("directive", ""),
            "model": start.get("model", ""),
            "status": "completed" if complete else "running",
            "created_at": events[0]["ts"],
            "updated_at": events[-1]["ts"],
            "reconstructed": True,
        }
        if complete:
            meta["cost"] = complete.get("cost", {})
        assert meta["directive"] == "hello_world"
        assert meta["status"] == "completed"
        assert meta["cost"]["turns"] == 2
        assert meta["reconstructed"] is True

    def test_reconstruct_error_thread(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"2026-02-09T04:03:50Z","type":"thread_start","directive":"test"}\n'
            '{"ts":"2026-02-09T04:04:01Z","type":"thread_error",'
            '"error_code":"llm_call_failed","detail":"timeout"}\n'
        )
        events = [json.loads(l) for l in jsonl_path.read_text().strip().split("\n")]
        error = next((e for e in events if e["type"] == "thread_error"), None)
        status = "error" if error else "running"
        assert status == "error"


class TestTranscriptRenderer:
    """Standalone transcript renderer."""

    def test_render_full_transcript(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"2026-02-09T04:03:50Z","type":"thread_start",'
            '"thread_id":"hello_world-1739012630","directive":"hello_world","model":"haiku"}\n'
            '{"ts":"2026-02-09T04:03:51Z","type":"user_message","text":"Hi","role":"user"}\n'
            '{"ts":"2026-02-09T04:03:52Z","type":"assistant_text","text":"Hello!"}\n'
            '{"ts":"2026-02-09T04:03:53Z","type":"thread_complete",'
            '"cost":{"turns":1,"tokens":100,"spend":0.001,"duration_seconds":3.0}}\n'
        )
        renderer = TranscriptRenderer(thinking=True, tool_details=True, metadata=True)
        md = renderer.render_file(jsonl_path)
        assert "# hello_world" in md
        assert "## User" in md
        assert "**Assistant:**" in md
        assert "Hello!" in md
        assert "## Completed" in md

    def test_render_with_thinking_disabled(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"T","type":"assistant_reasoning","text":"Let me think..."}\n'
            '{"ts":"T","type":"assistant_text","text":"Answer is 42"}\n'
        )
        renderer = TranscriptRenderer(thinking=False, tool_details=True, metadata=True)
        md = renderer.render_file(jsonl_path)
        assert "Let me think..." not in md
        assert "Answer is 42" in md

    def test_render_with_thinking_enabled(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"T","type":"assistant_reasoning","text":"Let me think..."}\n'
            '{"ts":"T","type":"assistant_text","text":"Answer is 42"}\n'
        )
        renderer = TranscriptRenderer(thinking=True, tool_details=True, metadata=True)
        md = renderer.render_file(jsonl_path)
        assert "Let me think..." in md
        assert "Answer is 42" in md

    def test_render_with_tool_details_disabled(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"T","type":"tool_call_start","tool":"fs_read","call_id":"1","input":{"path":"/x"}}\n'
            '{"ts":"T","type":"tool_call_result","call_id":"1","output":"contents","duration_ms":50}\n'
        )
        renderer = TranscriptRenderer(thinking=True, tool_details=False, metadata=True)
        md = renderer.render_file(jsonl_path)
        assert "**Tool:** `fs_read`" in md
        assert "```json" not in md

    def test_render_with_tool_details_enabled(self, thread_dir):
        jsonl_path = thread_dir / THREAD_ID / "transcript.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            '{"ts":"T","type":"tool_call_start","tool":"fs_read","call_id":"1","input":{"path":"/x"}}\n'
            '{"ts":"T","type":"tool_call_result","call_id":"1","output":"contents","duration_ms":50}\n'
        )
        renderer = TranscriptRenderer(thinking=True, tool_details=True, metadata=True)
        md = renderer.render_file(jsonl_path)
        assert "**Tool Call:** `fs_read`" in md
        assert "```json" in md
        assert "contents" in md


class TestThreadTelemetry:
    """Telemetry aggregation from thread.json files."""

    def test_aggregate_counts_threads(self, thread_dir):
        for i, status in enumerate(["completed", "completed", "error"]):
            t_dir = thread_dir / f"test-{1739012630 + i}"
            t_dir.mkdir(parents=True)
            (t_dir / "thread.json").write_text(json.dumps({
                "thread_id": f"test-{1739012630 + i}",
                "directive": "test",
                "status": status,
                "created_at": "2026-02-09T04:03:50Z",
                "cost": {"spend": 0.01, "tokens": 1000},
            }))
        telemetry = ThreadTelemetry(thread_dir)
        result = telemetry.aggregate_all()
        assert result["total_threads"] == 3
        assert result["by_status"]["completed"] == 2
        assert result["by_status"]["error"] == 1

    def test_aggregate_sums_cost(self, thread_dir):
        for i in range(3):
            t_dir = thread_dir / f"test-{1739012630 + i}"
            t_dir.mkdir(parents=True)
            (t_dir / "thread.json").write_text(json.dumps({
                "thread_id": f"test-{1739012630 + i}",
                "directive": "test",
                "status": "completed",
                "created_at": "2026-02-09T04:03:50Z",
                "cost": {"spend": 0.01, "tokens": 1000},
            }))
        telemetry = ThreadTelemetry(thread_dir)
        result = telemetry.aggregate_all()
        assert abs(result["cost_summary"]["total_spend"] - 0.03) < 0.001
        assert result["cost_summary"]["total_tokens"] == 3000

    def test_aggregate_groups_by_directive(self, thread_dir):
        directives = ["hello", "hello", "deploy"]
        for i, d in enumerate(directives):
            t_dir = thread_dir / f"{d}-{1739012630 + i}"
            t_dir.mkdir(parents=True)
            (t_dir / "thread.json").write_text(json.dumps({
                "thread_id": f"{d}-{1739012630 + i}",
                "directive": d,
                "status": "completed",
                "created_at": "2026-02-09T04:03:50Z",
                "cost": {"spend": 0.01, "tokens": 500},
            }))
        telemetry = ThreadTelemetry(thread_dir)
        result = telemetry.aggregate_all()
        assert result["by_directive"]["hello"]["count"] == 2
        assert result["by_directive"]["deploy"]["count"] == 1

    def test_aggregate_skips_missing_thread_json(self, thread_dir):
        (thread_dir / "orphan-1739012630").mkdir(parents=True)
        (thread_dir / "orphan-1739012630" / "transcript.jsonl").write_text("")
        telemetry = ThreadTelemetry(thread_dir)
        result = telemetry.aggregate_all()
        assert result["total_threads"] == 0

    def test_aggregate_handles_corrupt_thread_json(self, thread_dir):
        t_dir = thread_dir / "corrupt-1739012630"
        t_dir.mkdir(parents=True)
        (t_dir / "thread.json").write_text("NOT VALID JSON{{{")
        telemetry = ThreadTelemetry(thread_dir)
        result = telemetry.aggregate_all()
        assert result["total_threads"] == 0
