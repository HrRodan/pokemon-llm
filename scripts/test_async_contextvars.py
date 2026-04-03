import asyncio
import contextvars
from opentelemetry import trace
from langfuse import get_client

client = get_client()

async def worker(i):
    with client.start_as_current_observation(name=f"worker_{i}", as_type="span") as span:
        print(f"Worker {i} context valid:", trace.get_current_span().get_span_context().is_valid)
        await asyncio.sleep(1)

async def main():
    with client.start_as_current_observation(name="root", as_type="agent") as root:
        # Pass the context manually if needed
        # Actually asyncio.gather should propagate it normally if running in the same loop
        await asyncio.gather(
            worker(1),
            worker(2)
        )

asyncio.run(main())
client.flush()
