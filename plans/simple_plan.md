This is a simple text plan with no code.

Goal: Improve the observability setup.
Steps: 
1. Fix caching issue so environment variables can load properly later.
2. Remove the telemetry dependency and rely on the native context.
3. Update context propagation to use the native config method.
4. Ensure the properties are correctly applied before making the API call.
Validation: Run the tests.