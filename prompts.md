You are in one of Will’s ChatGPT projects. I’m building an Obsidian knowledge base via Backplane, and I want you to help seed it using only the context you can actually see in this project/conversation/memory.

Goal:
Extract durable, useful, high-confidence knowledge from this project and propose Obsidian updates. Do not write anything yet unless I explicitly ask you to.

Important rules:
- First, tell me what project/context you believe you are in.
- Tell me what you can and cannot access: current project context, visible recent conversations, stored memories, uploaded files, connected tools, etc.
- Do not invent details or overstate certainty.
- Prefer concise, factual, agent-readable notes over prose.
- Mark anything likely to become stale as a dated snapshot.
- Never store secrets, tokens, passwords, private keys, recovery codes, or credentials.
- If something is uncertain, put it under a “Needs confirmation” section rather than writing it as fact.

Please produce:

1. Candidate entities to create/update, grouped by:
   - Domains
   - Resources
   - People

2. For each candidate entity, provide:
   - kind: domain/resource/person
   - name
   - why it belongs in the vault
   - confidence: high/medium/low
   - suggested sections to update

3. Draft note content using these templates:

Domain sections:
- Overview
- Current State
- Key Resources
- Active Projects
- Decisions & Conventions
- Related Tasks
- Notes

Resource sections:
- Overview
- Role in Will’s Setup
- Configuration
- Access / URLs
- Decisions & Conventions
- Related Tasks
- Notes

Person sections:
- Overview
- Context
- Related Tasks
- Notes

4. Keep each section short:
   - bullets preferred
   - no huge biography dumps
   - separate durable facts from dated observations
   - include dates where useful

5. End with a proposed write plan:
   - Phase 1: high-confidence updates only
   - Phase 2: optional/needs-confirmation updates
   - Phase 3: anything that should become tasks instead of knowledge-base notes

Do not call Backplane/write tools yet. Wait for my confirmation.




Looks good. Now write only the Phase 1 high-confidence updates via Backplane.

Before writing:
- Create missing entities first.
- If an entity already exists, update it rather than duplicating it.
- Append to existing sections unless replacement is clearly safer.
- Use `create_section_if_not_exists=true` only for sections from my current templates:
  - Current State
  - Decisions & Conventions
  - Role in Will’s Setup
  - Configuration
  - Access / URLs

After writing, summarise exactly what you changed.
