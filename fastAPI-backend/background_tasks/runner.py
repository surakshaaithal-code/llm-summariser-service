import asyncio
from typing import Callable, Coroutine, Any


BackgroundCallable = Callable[[], Coroutine[Any, Any, None]]


async def run_in_background(task_fn: BackgroundCallable) -> None:
    """
    Schedule an async callable to run in the background without blocking the request.
    """
    asyncio.create_task(task_fn())
