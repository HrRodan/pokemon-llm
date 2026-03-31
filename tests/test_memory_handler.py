from ai_tools.memory import MemoryHandler

def test_handler_auto_generates_thread_id():
    handler = MemoryHandler()
    assert handler.thread_id is not None
    assert len(handler.thread_id) > 10

def test_handler_custom_thread_id():
    handler = MemoryHandler(thread_id="custom-123")
    assert handler.thread_id == "custom-123"

def test_handler_save_and_load():
    handler = MemoryHandler(thread_id="t1")
    step_id = handler.save_checkpoint([{"role": "user"}])
    assert step_id == 1
    
    history = handler.load_history()
    assert len(history) == 1
    assert history[0]["role"] == "user"

def test_handler_step_id_increments():
    handler = MemoryHandler(thread_id="t1")
    step1 = handler.save_checkpoint([{"msg": "1"}])
    step2 = handler.save_checkpoint([{"msg": "2"}])
    assert step1 == 1
    assert step2 == 2
    assert handler.step_id == 2

def test_handler_switch_thread():
    handler = MemoryHandler(thread_id="t1")
    handler.save_checkpoint([{"msg": "1"}])
    
    handler.switch_thread("t2")
    assert handler.step_id == 0
    handler.save_checkpoint([{"msg": "2"}])
    assert handler.step_id == 1
    
    handler.switch_thread("t1")
    assert handler.step_id == 1
    assert handler.load_history()[0]["msg"] == "1"

def test_handler_switch_to_nonexistent_thread():
    handler = MemoryHandler(thread_id="new_thread")
    assert handler.step_id == 0
    assert handler.load_history() == []

def test_handler_rollback():
    handler = MemoryHandler(thread_id="t1")
    handler.save_checkpoint([{"msg": "1"}])
    handler.save_checkpoint([{"msg": "2"}])
    handler.save_checkpoint([{"msg": "3"}])
    
    handler.rollback(1)
    assert handler.step_id == 1
    assert handler.load_history()[0]["msg"] == "1"

def test_handler_delete_active_thread():
    handler = MemoryHandler(thread_id="t1")
    handler.save_checkpoint([{"msg": "1"}])
    assert handler.thread_id == "t1"
    
    handler.delete_thread("t1")
    assert handler.thread_id != "t1"
    assert handler.step_id == 0

def test_handler_list_threads():
    handler = MemoryHandler(thread_id="t1")
    handler.save_checkpoint([{"msg": "1"}])
    handler.switch_thread("t2")
    handler.save_checkpoint([{"msg": "2"}])
    
    threads = handler.list_threads()
    assert len(threads) == 2

def test_handler_list_checkpoints():
    handler = MemoryHandler(thread_id="t1")
    handler.save_checkpoint([{"msg": "1"}])
    handler.save_checkpoint([{"msg": "2"}])
    cps = handler.list_checkpoints()
    assert len(cps) == 2
    
def test_handler_create_scoped_handler():
    handler = MemoryHandler(thread_id="parent")
    handler.save_checkpoint([{"msg": "parent"}])
    
    scoped = handler.create_scoped_handler("subagentX")
    assert scoped.thread_id != "parent"
    assert "subagentX" in scoped.thread_id
    assert scoped.step_id == 0
    
    # Both share the same backend, check listing
    threads = handler.list_threads()
    assert len(threads) == 1  # subagent hasn't saved yet
    
    scoped.save_checkpoint([{"msg": "child"}])
    assert len(handler.list_threads()) == 2
