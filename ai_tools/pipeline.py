"""
pipeline.py — LangChain-style pipe operator support for LLMQuery.

Provides three lightweight classes that implement Python's ``|`` operator so
that prompts and query objects can be chained left-to-right:

    result = "Explain AI" | query1 | query2 | print

How it works
------------
- ``LLMQuery.__ror__`` receives a string on the left side of ``|`` and calls
  ``invoke()`` on it, returning a ``_PipeableString``.
- ``_PipeableString`` is a ``str`` subclass that also implements ``__or__``,
  so the result of one step can flow into the next step automatically.
- ``_PipeableQuery`` wraps a ``LLMQuery`` together with per-call kwargs so
  that ``llm(model="openai/gpt-4o-mini")`` returns something pipeable without
  immediately executing the query.
- ``_Pipeline`` composes any two steps into a single reusable callable.
"""

from typing import Any


class _Pipeline:
    """
    Composes two pipeline steps so that ``step1 | step2`` creates a
    reusable callable that chains their execution left-to-right.

    This is created automatically when you write ``query1 | query2``.
    It is itself pipeable, so pipelines can be arbitrarily chained::

        pipeline = (query1 | query2) | query3
        result = "Hello" | pipeline
    """

    def __init__(self, step1: Any, step2: Any) -> None:
        """
        Store the two pipeline stages.

        Args:
            step1: Left stage — must support ``__ror__``.
            step2: Right stage — must support ``__ror__``.
        """
        self.step1 = step1
        self.step2 = step2

    def __ror__(self, input_data: Any) -> Any:
        """
        Execute the pipeline when used as the right-hand operand of ``|``.

        Pipes ``input_data`` through step1 first, then the result through
        step2.  Both steps must implement ``__ror__``.
        """
        # Pass input_data to step1 (triggers step1.__ror__)
        intermediate = input_data | self.step1
        # Then pass the result to step2
        return intermediate | self.step2

    def __or__(self, next_step: Any) -> "_Pipeline":
        """
        Allow further chaining: ``pipeline | another_step``.

        Returns a new ``_Pipeline`` so chaining is composable without limits.
        """
        return _Pipeline(self, next_step)

    def __call__(self, input_data: Any) -> Any:
        """
        Allow calling the pipeline directly as a function.

        Equivalent to ``input_data | self``.
        """
        return self.__ror__(input_data)


class _PipeableString(str):
    """
    A string subclass that allows piping its value into callables.

    Returned by ``LLMQuery.__ror__`` so that the output of one step can
    automatically flow into the next step via ``|``::

        result = "text" | query1 | query2

    Without this subclass, the built-in ``str.__or__`` raises ``TypeError``
    because plain strings don't know about our pipe protocol.
    """

    def __or__(self, other: Any) -> Any:
        """
        Pipe this string value into ``other``.

        If ``other`` defines ``__ror__``, yield control to it (Python's
        standard protocol — avoids the ambiguous case where both sides claim
        ownership of the ``|`` operation).  Otherwise, call ``other`` as a
        plain callable (e.g. ``print``).
        """
        if hasattr(other, "__ror__"):
            # Let the right-hand side handle it via the normal Python protocol.
            # Returning NotImplemented tells Python to try other.__ror__(self).
            return NotImplemented
        if callable(other):
            return other(self)
        return NotImplemented


class _PipeableQuery:
    """
    A wrapper for a ``LLMQuery`` instance that captures optional per-call
    keyword arguments and defers actual execution until piped::

        # Deferred: create the wrapper without firing the query
        step = llm_query(model="openai/gpt-4o-mini")

        # Execute: fire the query when piped
        result = "Explain AI" | step

    This is returned by ``LLMQuery.__call__(**kwargs)`` so that callers can
    parameterise a query step inline with ``|``.
    """

    def __init__(self, query_instance: Any, query_kwargs: dict) -> None:
        """
        Store the LLMQuery and the deferred kwargs.

        Args:
            query_instance: The ``LLMQuery`` (or compatible) instance to invoke.
            query_kwargs: Extra keyword arguments forwarded to ``invoke()``.
        """
        self.query_instance = query_instance
        self.query_kwargs = query_kwargs

    def __ror__(self, other: Any) -> Any:
        """
        Execute the wrapped query when data is piped in from the left.

        Accepts strings, lists of message dicts, and plain dicts — the same
        types accepted by ``LLMQuery.invoke()``.  The result is wrapped in
        ``_PipeableString`` if it is a ``str``, so it can be chained further.
        """
        if isinstance(other, (str, list, dict)):
            result = self.query_instance.invoke(other, **self.query_kwargs)
            # Wrap the output so it remains pipeable for subsequent steps
            return _PipeableString(result) if isinstance(result, str) else result
        return NotImplemented

    def __or__(self, other: Any) -> _Pipeline:
        """
        Continue building the pipeline without executing yet.

        Returns a new ``_Pipeline`` that chains this step with ``other``.
        """
        return _Pipeline(self, other)
