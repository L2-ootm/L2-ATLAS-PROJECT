# ULTRAREVIEW — `atlas_actor` Hermes dispatch failure

## Root cause: plugin handler ABI mismatch

**Exact failure points:**

- `services/agent-runtime/atlas_runtime/actor_bridge.py:137-145`
- `foundation/atlas-hermes/tools/registry.py:390-416`
- `foundation/atlas-hermes/model_tools.py:837-849`

The ATLAS bridge registered a schema-style handler:

```python
def atlas_actor_tool(op="status", ..., parent_agent=None) -> str:
    ...
```

Hermes plugin handlers instead receive the model arguments as one positional
dictionary and framework context as keyword arguments:

```python
return entry.handler(args, **kwargs)
```

The model dispatch always supplies `task_id` and `user_task` as context. Python
therefore rejects the call before the bridge's fail-open `try` block with
`TypeError: atlas_actor_tool() got an unexpected keyword argument 'task_id'`.
Merely adding a `task_id` parameter would reveal the second defect: the
positional dictionary would bind to `op`, so every valid invocation would still
fall through as an unknown operation.

## Chain of failure

1. Hermes parses the model call into `function_args`.
2. `model_tools.handle_function_call` calls `registry.dispatch` with that dict
   plus `task_id` and `user_task` framework context.
3. `ToolRegistry.dispatch` calls the registered handler as
   `handler(args, **kwargs)`.
4. The ATLAS handler has the wrong ABI and raises before actor validation or
   `spawn_actor`; consequently no actor or lifecycle row exists.
5. The registry converts the exception into a JSON tool error. Hermes can keep
   the model loop alive, allowing the parent to return a normal answer and the
   enclosing ATLAS run to be summarized as succeeded despite the failed tool.

## Related coverage gap

The actor bridge tests called `atlas_actor_tool` directly with named arguments.
That proves the service logic but bypasses the plugin registry contract and all
framework-injected context. Regression coverage must register the bridge and
invoke `model_tools.handle_function_call` or `registry.dispatch` with the exact
production call shape. It must assert that the run is resolved from Hermes's
`task_id`, an actor row is created, and no tool-dispatch error is returned.

## Related root cause: wrong schema envelope

**Exact failure point:** `services/agent-runtime/atlas_runtime/actor_bridge.py:38-87`

The bridge passed a full OpenAI wire tool object (`type: function` with a nested
`function`) to `PluginContext.register_tool`. Hermes plugin schemas are already
the inner function definition and must expose `name`, `description`, and
`parameters` at the top level. The extra envelope made Hermes publish the tool
with no defined parameters. The model consequently saw neither `op` nor `goal`
and produced an empty invocation. Existing tests inspected the ATLAS constant
or called the handler directly; none resolved the registered schema through
Hermes's normal tool-definition path.

## Related root cause: explicit run mapping overwritten with an empty value

**Exact failure points:**

- `services/agent-runtime/atlas_audit/__init__.py:125-139`
- `services/agent-runtime/atlas_runtime/agents/native.py:651-655`

ATLAS explicitly maps the harness session/run ID before constructing the Hermes
agent. Hermes later invokes the generic `on_session_start` hook with a session
ID but no ATLAS run ID. The audit hook stored that empty string over the valid
mapping. Once the native adapter correctly reused the run ID as Hermes's
`task_id`, actor lookup returned `""`; the actor insert then failed its
`parent_run_id REFERENCES runs(id)` foreign key. Empty hook notifications must
preserve explicit mappings, and the actor bridge must normalize falsy mapping
values to unavailable rather than attempting a database mutation.
