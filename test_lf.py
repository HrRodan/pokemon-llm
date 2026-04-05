import os
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-1"
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-1"
os.environ["LANGFUSE_BASE_URL"] = "http://test"
try:
    from langfuse import context
    print("context:", dir(context))
except Exception as e:
    print("error:", e)
