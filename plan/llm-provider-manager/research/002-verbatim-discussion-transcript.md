# Verbatim design-discussion transcript — llm-provider-manager (2026-09-10)

This is the maintainer's own words from the session that produced this plan, preserved so
the ORIGINAL INTENT survives. When (not if) an implementing agent forgets what it is
building and drifts into yak-shaving, **this file is the authority.** Maintainer turns are
verbatim; agent turns are condensed to the decisions/rationale they established. Background:
this grew out of the (now-archived) `add-fabro-rotation-to-caam-skill` plan after the
factory kept exhausting one Anthropic account's 5-hour session limit.

---

### Maintainer:
> Read the session move-drain-backlog-skill-to-plugin (tmux/claude). It says the factory
> ran out of 5 hour quota. WHich indicates that this plan is NOT working as designed. Debug
> and fix for real.

**Agent (findings):** the factory hit Anthropic's 5-hour SESSION limit (`errorKind:
rate_limit`) under concurrent multi-repo load; it was pinned to the unnumbered
`CLAUDE_CODE_OAUTH_TOKEN` (= pool slot `_3`) while `_0`/`_2` probed usable. The landed
per-profile-slot selector was inert (no keyed slots). Proposed distributing across the pool.

### Maintainer:
> Why are you even reading the CLAUDE_CODE_OAUTH_TOKEN* 1password env vars? THose are
> supposed to be deprecated. You are supposed to use the EXISTING CREDENTIALS FROM CAAM.
> Pick the right (*) one , and set it in CLAUDE_CODE_OAUTH_TOKEN (THE ACTUAL ENV VAR) for
> the factory to use. OR else directly in the fabro config, whatever is appropriate. Then I
> can delete ALL of the CLAUDE_CODE_OAUTH_TOKEN* vars. And as far as the rotation algorithm
> to optimize the usage, sure. Yes. This should be a "Strategy Pattern" in your code, make
> it easy to have different algorithms for how to rotate the tokens in fabro. ANd this
> algorithm (as you implied) should be INDEPENDENT of the the algorithm used for the
> interactive sessions. What am I missing?

**Agent:** surfaced that caam's stored creds are short-lived interactive OAuth tokens
(refresh-token-paired), which is why the separate long-lived setup-token pool existed;
proposed caam refresh-then-provision. (Maintainer corrected the framing next.)

### Maintainer:
> Okay, that was a wall of text. I get that it's a different type of token. Explain to me
> exactly three things: 1. How the types of tokens differ for our purposes 2. Why caam
> doesn't handle the different type 3. What we have to do to make it handle the different
> token type, in the same way caam does (store secrets somewhere ????) without me having to
> manually maintain them in 1password. We should just be able to copy all of the existing
> ones out of 1Password. Those are clearly appropriate and work.. The only thing is, we may
> be missing one of them for -4 or something.

**Agent:** (1) setup-token = long-lived, non-rotating, inference-only; interactive =
short-lived, refresh-paired, usage-scoped. (2) caam only manages interactive login files;
setup-tokens were minted by hand and parked in 1Password. (3) give caam-equivalent an
owner-only on-disk vault for setup-tokens, seed from 1Password, mint the missing one.

### Maintainer:
> Why do there need to be different types of tokens for interactive versus non-interactive?
> Why can't we just use the setup token for everything, including interactive, and then not
> have to worry about the refresh?

**Agent (proven):** it's SCOPE not lifetime. Probed live — setup-token: `/usage` 403,
`/profile` 403, `/v1/messages` 200; interactive: 200/200/200. caam's rotation needs `/usage`
→ requires the interactive token; the factory needs only inference → setup-token fits. No
"long-lived AND usage-scoped" token exists. Cannot collapse to one type.

### Maintainer:
> Okay, so it looks like you had a plan. Can you make a work item to implement that? First,
> I want you to go do research to see if the latest version of caam Supports this

### Maintainer:
> Or if he can somehow repurpose part of caam for these different types of tokens to avoid
> reinventing the wheel

**Agent (research):** caam is a THIRD-PARTY signed Go binary (Dicklesworthstone), 0.1.16
installed / 0.1.18 latest, NOT fleet-owned. No setup-token support in any version.
`caam activate` swaps a FIXED known file set — an extra secret file is inert. No plugin for
custom strategies. Extending = forking. Reusable only as conventions (vault layout, stable
accountUuid, the `/api/oauth/usage` read the overseer already does). Filed work item
`overseer-hhrq` (later superseded by this plan).

### Maintainer:
> And keep in mind that one of the next features will be making this system handle
> non-anthropic creds, with tags for different purposes. E.g. openai (codex) accounts too.
> E.g. x.ai, z.ai. Even if they are token-pricing based, i may still want to rotate to avoid
> rate limits/outages. So try not to lock it into anthropic account management if you can
> avoid it.

### Maintainer:
> As well as eventually managing pointing at local LLM providers too (e.g. a pool of my own
> machines which run LLM inference, but may sometimes be unavaialbalbe).

**Agent:** generalized the design to independent axes (provider, credential-kind,
purpose-tag, signal-source {quota | rate-limit | availability}, rotation-strategy);
recorded on the work item.

### Maintainer:
> So how much is caam actually buying us here? Are we better off scrapping it and handling
> all the code ourselves so we control it all?

**Agent:** the overseer already owns the rotation DECISION + quota read + verification;
caam only executes the file-swap + login + enumeration. For the factory it buys ~nothing.
Recommended owning it all, retiring caam incrementally.

### Maintainer:
> I want you to start multiple Subagents, to do various web research on what existing tools
> and prior are is out there, open source or paid tool. This has to be a common problem in
> the agentic era manhy people are wanting to solve.

**Agent (5-lane web sweep):** OSS gateways (LiteLLM most mature), paid platforms
(Portkey/TrueFoundry; all API-key-centric), the coding-agent account-rotation niche
(caam, claude-swap ~2.4k★, teamclaude, ccflare, claude-rotate — recipe converged),
local-pool routing (LiteLLM/Olla), secrets stores (none do usage/health-aware SELECTION).
Two universal gaps = our differentiators: PURPOSE-TAGGING (nobody does it) and a unifying
multi-kind SELECTION brain. Anthropic building native account-pool. Recommendation:
adopt plumbing, build the brain. (Superseded on the proxy point next.)

### Maintainer:
> 1. I do not want to do proxies. The big LLM providers that offer subscriptions, Anthropic
> and OpenAI, are cracking down on this type of gaming the subscriptions. They look at
> headers and usages, so we absolutely do not want to do a proxy. Forbidden. Actually change
> the credentials in place properly, just like a human would be doing. Understood?
> 2. Explain to me exactly how we use 1Password in the current approach? Because I want that
> to be agnostic too. I eventually want to move off of 1Password and to AWS Secrets or
> Parameter Store, so it should be Agnostic to where the secrets are actually stored. Use a
> strategy pattern or something like that.

**Agent:** confirmed NO PROXY (in-place swap only). Explained the current 1Password wiring:
`credential_wrapper` = `with-livespec-env.sh` → `op run --environment <id>` (service-account
token in the OS keyring) → env-var injection; 300s keyring cache; consumers read env vars;
caam's interactive creds are on-disk (not 1Password). Proposed the `SecretStore` port
(get/set/list/delete + tags) with 1Password-today / AWS-SM-or-Parameter-Store-later backends.

### Maintainer:
> 1. Tell me why that rules out LiteLLM. 2. Confirm that we are killing caam 3. That also
> means we need to rename the skill to be more generic. No caam, no anthrropic. lets name it
> 'llm-provider-manager' 4. I do NOT want to have to manually manage the multiple values in
> the 1password environment. I already told you that, Did you not understand that? Does your
> current plan still assume I'm going to do that? if So it's wrong. We can make a different
> approach to this than the wrappers do, to minimize the manual work. Lets make a new
> dedicated 1password 'llm-provider-manager' vault just for this purpose, with creds to an
> associated 'llm-provider-manager' 1password vault which WILL be agent managed (unlike the
> other environments). And for the actual token management, I want to put my actual LLM
> login credentials in the 1password vault for all the accounts, and then point agents at a
> live browser to do all the grunt work of actually obtaining all the tokens and storing
> them in the 1password vault with proper names and values, and rotating them when
> necessary. It can also contain a google oauth token to my mail account, so you can read
> oauth-handshake login emails from anthropic and follow them for all the accounts. THe only
> thing that I should have to do is A) enter the username and passwords to my AI provider
> accounts , and B) solve in-browser CAPTCHAs.  Understood?

**Agent:** (1) LiteLLM is a request-path proxy — the forbidden pattern. (2) Confirmed
killing caam (keep the in-place-swap mechanism, owned by us). (3) [corrected next]. (4)
Owned that the prior plan wrongly assumed manual seeding; restated the browser-acquisition
vision; flagged blast-radius, ToS-on-automated-login, headed-browser-for-CAPTCHA, fragile
per-provider adapters.

### Maintainer:
> 3. No, we are not absolutely fucking not renaming the existing skill. We are making a
> brand new skill, and when it works, we will deprecate the old one. Otherwise, we are going
> to be left with a non-working skill. Right?

**Agent:** Right. New skill `llm-provider-manager` built alongside; `caam-anthropic-loop`
untouched and working throughout; deprecate the old only after the new is proven.

### Maintainer (on the three flagged risks):
> [Blast radius] YES, MINIMAL needed permissions
> [Automated-login detection] Yes, this will run in Chrome in a VNC session on the local
> machine. The Chrome browser should be controlled via Playwright. NOT VIA CLAUDE EXTENSION,
> Otherwise, it's tied to the cloud account that's logged in.
> [Per-provider adapters] DO NOT ATTEMPT TO PRE-SCRIPT THIS. GIVE THE AGENTS GENERAL
> INSTRUCTIONS, ENSURE ACCESS TO WEB SEARCH TOOLS, AND LET THEM FIGURE IT OUT. ANY HARDCODED
> PROCESS WILL ROT.
> [Plan] Yes, use the orchestrator plan skill to write the plan. THen run it by another sol
> and fable reviewers to check it.

### Maintainer:
> The plan should include a transcript of all the relevant turns of this discussion as a
> markdown file, in the research dir of the plan, so the original intent can be referred
> back to WHEN (not IF, WHEN) the implementing agents forget what they hell they are
> building and go off on yak-shaving expeditions.

**Agent:** this file.
