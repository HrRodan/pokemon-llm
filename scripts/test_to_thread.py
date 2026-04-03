import asyncio
from opentelemetry import context, trace
from langfuse import get_client

client = get_client()

def blocking_io(i):
    with client.start_as_current_observation(name=f"worker_{i}", as_type="span") as span:
        print(f"Worker {i} context valid:", trace.get_current_span().get_span_context().is_valid)
        import time
        time.sleep(1)

async def main():
    with client.start_as_current_observation(name="root", as_type="agent") as root:
        await asyncio.gather(
            asyncio.to_thread(blocking_io, 1),
            asyncio.to_thread(blocking_io, 2)
        )

asyncio.run(main())
client.flush()
