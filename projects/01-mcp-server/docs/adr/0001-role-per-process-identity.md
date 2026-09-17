# ADR-0001: Bind authorisation to the process, not to the request

- **Status:** accepted
- **Date:** 2026-09-16
- **Author:** Armando Gomez

## Situation

`fde-mcp` exposes three sources to an AI client, and two of its tools change the world: one writes
incidents to the ops database, one messages the on-call chat. Something has to decide who may call those.

The constraint that shapes everything: **MCP over stdio has no request identity.** The transport is a pipe
between one client and one server process. There is no header to inspect, no session to authenticate, no
caller to look up. Whatever identity exists has to come from somewhere other than the request.

A second constraint is the audience. This runs at a customer site, configured by whoever sets up the MCP
client — often not the person who wrote it. A design that only holds when configured perfectly will not hold.

"Good" meant: a client cannot invoke a tool it shouldn't, the failure mode of a misconfiguration is *less*
access rather than more, and an engineer can tell what a given client may do by reading one file.

## Options considered

### Option A: One role per server process, set by `FDE_MCP_ROLE` (chosen)

The process starts as exactly one role. Tools outside that role's scopes are never registered, so they do
not appear in `tools/list` and cannot be called. A client that needs two levels of access registers the
server twice with different environment blocks.

- **Pros:** The model never sees a tool it can't use, so there is nothing to be talked into calling — which
  matters because tool output carries attacker-controlled text (see [ADR-0002](0002-untrusted-input-strategy.md)).
  Authorisation is decided once at startup, so there is no per-call path to get wrong. An unknown role
  yields zero tools, so a typo fails closed. The whole policy is one readable TOML file.
- **Cons:** No per-user identity — two people sharing a client share a role. Changing access means
  restarting the process. Registering the server twice is duplication a reviewer might not expect.

### Option B: Per-request identity via an auth token in the tool arguments

Each tool takes a `caller_token`; the server maps it to a role and checks per call.

- **Pros:** One process serves multiple privilege levels; access can change without a restart.
- **Cons:** Fatal for this threat model. Every tool must then be *registered* regardless of role, so the
  privileged tools are visible in the tool list, and the model decides which to call while reading text an
  attacker wrote. It also puts a credential into model-visible arguments, where it lands in logs and
  context windows — the opposite of keeping the Telegram token out of URLs. Rejected.

### Option C: HTTP transport with bearer tokens mapped to roles

Run as streamable HTTP, authenticate per request, register tools per session.

- **Pros:** Real multi-tenancy, per-user identity, revocation without restart, an audit trail keyed to a person.
- **Cons:** Buys a problem this deployment doesn't have. It adds a listening port, TLS, and token lifecycle
  to an on-prem box whose whole appeal is that it talks to a local database over a pipe. The MCP SDK
  supports per-session tool filtering, so this is viable later — but it is a different product. Deferred.

### Option D: Ask the user to confirm each side-effecting call (elicitation)

Let every write and every alert prompt the human through the client.

- **Pros:** No policy file; a human sees each action.
- **Cons:** Confirmation fatigue turns into reflexive approval, so it degrades to no control at all. It also
  depends on the client implementing elicitation. Useful *in addition to* scopes, not instead of. Deferred.

## Decision

**Option A.** With no request identity in the transport, the honest place to bind authorisation is the
process — and binding it there buys a property the alternatives can't offer: *the dangerous tool does not
exist in this process*. That is a stronger guarantee than a check, because it cannot be reasoned around by
a model, and it is the reason a prompt-injection payload naming `telegram_send_alert` hits nothing.

Enforcement is still doubled: the tool is not registered, *and* the handler re-checks its scope before
touching a source, so a future change that registers tools dynamically doesn't silently open a door.

## What it cost

- **No per-user accountability.** The incident row says a `db:write`-capable client wrote it, not which
  human. For a portfolio ops DB that's acceptable; for a regulated customer it would not be.
- **Restart to change access**, which in a real engagement means a maintenance window for a permission change.
- **Duplicate client registration**, and the room for error that creates: someone configuring two entries can
  give the wrong one the `oncall` role. The failure is quiet, because a role with *more* access looks like
  everything working. This is the weakest point of the design.
- **A policy file that can drift** from the tool registry. Mitigated by a load-time check: a role granting an
  undeclared scope fails at startup rather than granting nothing silently.

## What I would do differently / revisit

Revisit when any of these become true:

1. **More than one human uses the same client.** Per-user identity stops being optional the moment "who
   logged this incident" has an answer that matters.
2. **A shared or hosted deployment** is proposed — that's Option C, and it should be an HTTP service with
   bearer tokens mapped to roles, not this design with a token bolted into arguments.
3. **The outbox gets drained automatically.** A background sender acts with no client attached, which means
   an authorisation model with no process-bound role to inherit.

With hindsight I would still choose this, but I'd add an audit log of tool calls from day one. Right now the
evidence that a write happened is the row itself, and during an incident that is one source short of a story.
