from ai_tools.memory import MemoryHandler, InMemoryBackend

def test_initial_message_extraction():
    handler = MemoryHandler(backend=InMemoryBackend())
    
    # Save a checkpoint with a system message and a user message
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you today?"},
        {"role": "assistant", "content": "I am fine, thank you!"}
    ]
    
    handler.save_checkpoint(messages=messages)
    
    # Check that initial message was set
    threads = handler.list_threads()
    assert len(threads) == 1
    assert threads[0].initial_message == "Hello, how are you today?"

def test_short_thread_ids():
    handler = MemoryHandler(backend=InMemoryBackend())
    thread_id = handler.thread_id
    # Assert thread ID is 8 characters
    assert len(thread_id) == 8
