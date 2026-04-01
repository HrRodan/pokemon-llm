import pytest

from ai_tools.memory import InMemoryBackend, SQLiteBackend, ConversationState

@pytest.fixture(params=["in_memory", "sqlite"])
def backend(request, tmp_path):
    if request.param == "in_memory":
        return InMemoryBackend()
    else:
        return SQLiteBackend(db_path=str(tmp_path / "test.db"))

def test_save_and_load_checkpoint(backend):
    state = ConversationState(messages=[{"role": "user", "content": "hi"}])
    backend.save_checkpoint("t1", 1, state, "agentX")
    
    cp = backend.load_checkpoint("t1", 1)
    assert cp is not None
    assert cp.thread_id == "t1"
    assert cp.step_id == 1
    assert len(cp.state.messages) == 1
    assert cp.state.messages[0]["content"] == "hi"

def test_load_latest_checkpoint(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[{"content": "first"}]))
    backend.save_checkpoint("t1", 2, ConversationState(messages=[{"content": "second"}]))
    
    cp = backend.load_checkpoint("t1")  # step_id is None -> latest
    assert cp is not None
    assert cp.step_id == 2
    assert cp.state.messages[0]["content"] == "second"

def test_load_specific_checkpoint(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[{"content": "first"}]))
    backend.save_checkpoint("t1", 2, ConversationState(messages=[{"content": "second"}]))
    
    cp = backend.load_checkpoint("t1", 1)
    assert cp is not None
    assert cp.step_id == 1

def test_load_nonexistent_thread_returns_none(backend):
    assert backend.load_checkpoint("t_nope") is None

def test_get_history_returns_messages(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[{"content": "first"}, {"content": "second"}]))
    msgs = backend.get_history("t1")
    assert len(msgs) == 2
    assert msgs[0]["content"] == "first"

def test_get_history_with_limit(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[
        {"content": "1"}, {"content": "2"}, {"content": "3"}
    ]))
    msgs = backend.get_history("t1", limit=2)
    assert len(msgs) == 2
    assert msgs[0]["content"] == "2"

def test_get_history_empty_thread(backend):
    msgs = backend.get_history("t_nope")
    assert msgs == []

def test_list_threads(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[]), agent_name="agent_a")
    backend.save_checkpoint("t2", 1, ConversationState(messages=[]), agent_name="agent_b")
    
    threads = backend.list_threads()
    assert len(threads) == 2
    # Ensure they are returned
    t_ids = {t.thread_id for t in threads}
    assert "t1" in t_ids
    assert "t2" in t_ids

def test_list_threads_filter_by_agent(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[]), agent_name="agent_a")
    backend.save_checkpoint("t2", 1, ConversationState(messages=[]), agent_name="agent_b")
    
    threads = backend.list_threads(agent_name="agent_a")
    assert len(threads) == 1
    assert threads[0].thread_id == "t1"

def test_list_checkpoints(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[]))
    backend.save_checkpoint("t1", 2, ConversationState(messages=[]))
    backend.save_checkpoint("t2", 1, ConversationState(messages=[]))
    
    cps = backend.list_checkpoints("t1")
    assert len(cps) == 2
    assert cps[0].step_id == 1
    assert cps[1].step_id == 2

def test_rollback(backend):
    for i in range(1, 4):
        backend.save_checkpoint("t1", i, ConversationState(messages=[{"content": str(i)}]))
    
    backend.rollback("t1", 1)
    
    cps = backend.list_checkpoints("t1")
    assert len(cps) == 1
    assert cps[0].step_id == 1

def test_rollback_preserves_target(backend):
    for i in range(1, 4):
        backend.save_checkpoint("t1", i, ConversationState(messages=[{"content": str(i)}]))
    
    backend.rollback("t1", 2)
    cp = backend.load_checkpoint("t1")
    assert cp.step_id == 2

def test_delete_thread(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[]))
    assert backend.thread_exists("t1")
    
    backend.delete_thread("t1")
    assert not backend.thread_exists("t1")
    assert backend.load_checkpoint("t1") is None

def test_fork_thread(backend):
    for i in range(1, 4):
        backend.save_checkpoint("t1", i, ConversationState(messages=[{"content": str(i)}]))
    
    backend.fork_thread("t1", 2, "t2")
    
    # Check new thread exists
    assert backend.thread_exists("t2")
    
    # Check new thread has history up to step 2
    cps = backend.list_checkpoints("t2")
    assert len(cps) == 2
    assert cps[0].step_id == 1
    assert cps[1].step_id == 2
    
    # Check old thread is completely untouched
    old_cps = backend.list_checkpoints("t1")
    assert len(old_cps) == 3

def test_thread_exists(backend):
    assert not backend.thread_exists("t_nope")
    backend.save_checkpoint("t1", 1, ConversationState(messages=[]))
    assert backend.thread_exists("t1")

def test_thread_isolation(backend):
    backend.save_checkpoint("t1", 1, ConversationState(messages=[{"content": "t1"}]))
    backend.save_checkpoint("t2", 1, ConversationState(messages=[{"content": "t2"}]))
    
    assert backend.get_history("t1")[0]["content"] == "t1"
    assert backend.get_history("t2")[0]["content"] == "t2"

def test_auto_create_schema(tmp_path):
    import sqlite3
    db = tmp_path / "schema.db"
    SQLiteBackend(db_path=str(db))
    # Check tables directly with sqlite
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cur.fetchall()}
    assert "threads" in tables
    assert "checkpoints" in tables
