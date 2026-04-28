# Sandbox Provider Decision

## Decision

Yudai should continue using Modal as the only sandbox provider and should not add
a sandbox-provider abstraction yet.

## Rationale

There is no current second provider with concrete integration requirements,
operational constraints, or product behavior that would justify a provider
interface. Adding an abstraction now would mainly add indirection around Modal
setup, lifecycle, logs, configuration, and error handling without proving that
the interface matches a real alternate provider.

The existing Modal-specific code should stay explicit until a second provider
creates clear pressure for shared boundaries. That keeps the runtime easier to
debug and avoids designing around hypothetical behavior.

## Revisit Criteria

Reconsider this decision when at least one of these is true:

- A second sandbox provider is selected for implementation.
- Provider switching becomes a committed product or deployment requirement.
- Modal-specific lifecycle or configuration code blocks a necessary runtime
  change.
- Tests need provider-independent behavior that cannot be covered with narrow
  fakes around the existing Modal integration.

## Follow-up

When those criteria are met, start with a small design note describing the real
second provider, the exact operations that must vary, and the smallest interface
needed to support both implementations.
