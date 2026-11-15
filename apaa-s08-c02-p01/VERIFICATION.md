# Verification — APAA-S08-C02-P05

## Runtime integration
- Task factory and the queue-submission trust boundary apply P04 action/payload validation; direct Task construction is regression-tested.
- Tasks persist a policy version; schema migration preserves existing task rows with v1 default.
- ExecutionEngine now owns/injects PolicyRegistry and ConsentRegistry.
- Policy is deny-by-default and must match both action and policy version.
- Explicit consent is persisted as a task-scoped grant with 15-minute default TTL.
- Consent revocation and policy disablement are checked at execution time.
- Handler is not invoked if permission, policy, consent, or handler registration is missing.

## Added regression cases
- Missing policy blocks execution.
- Policy revoked after submission blocks execution.
- Consent revoked after submission blocks execution.
- Expired consent blocks execution.
- Invalid action and unsafe payload rejected before queueing.
- Prior queue, retry, lease, dead-letter, audit, P04 validation, policy, consent, and backup tests remain in the suite.

## Security limits
- Consent is represented by the caller's explicit `user_consented=True` input; a real application UI must ensure this flag can only follow actual user approval.
- Authorization is rechecked immediately before handler invocation, but this in-process design does not provide an atomic lock across the authorization check and arbitrary external side effect.
- No production deployment, external adapter, payments, purchases, network or device control is included.
