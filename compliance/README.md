# compliance/ — SOC 2 control mapping (Gap 4)

Maps each existing control to the SOC 2 **Trust Services Criteria** it supports. Read a SOC 2
**Type II** primer first so the terminology is correct (criteria vs. controls, CUECs, the
"suitably designed and operating effectively over a period" framing). See
[`../PLAN.md`](../PLAN.md#phase-5--soc-2-mapping--the-runbook-weekend-3-closes-gap-4--the-fde-artifact)
Phase 5.

## Planned file

`soc2-control-mapping.md` — a table plus plain-English implementation + evidence notes.

| Control (as built here) | Trust Services Criteria it supports |
|---|---|
| Append-only audit stream | CC7.2 / CC7.3 (monitoring & evaluation), availability evidence |
| One-shot action tokens | CC6.1, CC6.6 (logical access, least privilege) |
| Default-deny trust ladder | CC6.1, CC6.3 |
| Network isolation (default-deny NetworkPolicy) | CC6.6, CC6.7 |
| Secret rotation (Secrets Manager) | CC6.1, CC6.7 |

Each row in the final file gets: *how it's implemented here*, *where in the repo*, and *what an
auditor would sample as evidence*.

> Scope note: this is a **control-to-criteria mapping** to demonstrate security literacy — it
> is not an assertion that the reference deployment is SOC 2 certified.
