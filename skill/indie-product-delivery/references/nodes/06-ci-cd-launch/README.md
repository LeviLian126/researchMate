# Release Execution

Node06 prepares or executes a release as a controlled external operation. It owns target and artifact identity, environment and credential boundaries, CI/CD mechanics, rollout sequencing, migration/provider execution, recovery, immediate verification, and durable release state.

| Need | Read |
|---|---|
| establish target, source, authorization, Node05 evidence, environment, pipeline, credentials, and readiness | `release-readiness-environment-and-pipeline.md` |
| execute an authorized rollout, migration, provider action, recovery, smoke/watch, and release record | `rollout-recovery-verification-and-record.md` |

Release preparation and execution are different terminal targets. Use `PLAN_ONLY` while target, evidence, recovery, access, or exact authorization is incomplete. Use `READY_TO_EXECUTE` only when the intended environment, source artifact/ref, commands or workflow inputs, exclusions, gates, and recovery path are current. Use `EXECUTED_AND_VERIFIED` only after the authorized action and required immediate proof pass.

Do not infer production authority from “ship it,” a feature implementation request, a green CI run, or access credentials alone. Exact authorization must cover the action and target, including migrations, data writes, provider calls, DNS, payment, traffic, rollback, or disable behavior where relevant.

Never disable required tests, bypass protected environments, broaden credentials, interpolate untrusted event text into shells, or substitute optimism for rollback/forward-fix/manual recovery. Return stale quality evidence to Node05, contract or recovery design to Node02, and application defects to Node03/04.

Hand stable ongoing health and customer learning to Node07 only after immediate release or incident state is recorded. A preparation request may finish successfully at release-ready; an execution request without authority or access is blocked rather than described as released.
