How AI Agents Remember Things
February 17, 2026
•
8 min read
ai-agents
agent-memory
context-engineering
developer-productivity
Out of the box, AI agents have no memory. Every conversation starts with a blank slate.

Most people assume you need vector databases, complex retrieval pipelines, or specialized memory infrastructure to fix this. But it turns out the storage is the easy part. The hard part is knowing when to write and when to load. Get that right, and the rest is just files.

Prefer video? Watch How AI Agents Remember Things on YouTube →

I’ll use OpenClaw as a case study here. Its memory model is one of the clearest real-world implementations I’ve seen. But the patterns apply to any agent you build.

Why Agents Have No Memory By Default
AI models are inherently stateless. There’s no memory between calls. What looks like a conversation is just an increasingly long context window being passed on each turn. Every message, every response, every tool call gets appended to the transcript and sent with the next request.

This works fine for a one-off question. It breaks down the moment you want an agent that knows you.

Memory systems handle this by splitting the problem in two: the session, and longer-term memory.

Sessions
A session is the history of a single conversation with an LLM. While the conversation is active, that history gets passed along with each call, and the model can see everything said so far. But LLMs have finite context windows, and as you approach that limit, something has to give.

That something is compaction. Compaction takes the session’s conversation history and condenses it down to the most important information so the conversation can continue. There are three different strategies for triggering it:

Count-based: compact once the conversation exceeds a certain token size or turn count
Time-based: triggered when the user stops interacting for a period of time, handled in the background
Event-based: an agent detects that a task or topic has concluded and triggers compaction. The most intelligent approach, but also the hardest to implement accurately
The shared problem with all three: you can’t simply carry entire old conversations forward into a new session. Context windows don’t allow it. That’s where long-term memory comes in.

Think of it as a desk and a filing cabinet. The session is the messy desk, with notes scattered around and documents open. Memory is the filing cabinet where things are categorized and stored for later. When the session ends, whatever isn’t filed is gone.

The Memory Taxonomy
Google published a whitepaper in November 2025 titled “Context Engineering: Sessions & Memory” that provides a useful framework for thinking about this. It breaks agent memory into three types.

Episodic memory covers events and interactions. “What happened in our last conversation?” If you spent a session debugging a webhook integration, episodic memory is what lets the agent recall that context in your next conversation.

Semantic memory is facts and preferences. “What do I know about this user?” Tech stack, coding style, project conventions. These are stable facts that don’t change much from session to session.

Procedural memory is workflows and learned routines. “How do I accomplish this task?” The agent’s understanding of your deployment process, your testing patterns, your PR review checklist.

All three work together to form what we’d call an agent’s memory. The challenge isn’t categorizing them. It’s extracting them from conversation and keeping them accurate over time.

Extraction and Consolidation
In order for a memory system to be effective, it needs to extract the right things from a conversation. Not every detail is worth keeping. Targeted filtering is necessary, the same way human memory doesn’t retain every word of a conversation. It retains key facts and decisions.

Beyond that, the system needs to consolidate. Consider a user who tells an agent “I prefer dark mode” in one session, then later says “I like dark mode,” and in another session mentions “I switched to dark mode.” Without consolidation, all three entries sit in memory saying essentially the same thing. A good memory system collapses those into a single entry: “User prefers dark mode.”

It also needs to handle updates. Something true today might not be true tomorrow. If you switch from dark mode to light mode, the memory system needs to overwrite the old entry, not append a contradictory one. Without this, memory becomes noisy and unreliable over time.

Both extraction and consolidation are typically handled by a separate LLM instance that takes a conversation and processes it, deciding what to keep, what to merge, and what to update.

Memory Storage
Storage itself is relatively straightforward. For local agents, markdown files work well. They’re readable, debuggable, and require no infrastructure. For agents that need semantic search across a large history, a vector database is the right tool. The choice depends on the use case.

What matters more than the storage format is the shape of what you store: semantic memory for stable facts, episodic memory for events and recent context, and procedural memory for workflows.

OpenClaw’s Memory Model
Let me walk through how one system actually implements this.

OpenClaw’s memory system has three core components, and all of them are just markdown files.

MEMORY.md is the semantic memory store. Stable facts, user preferences, identity information. It has a recommended 200-line cap and is organized into structured sections. The key design decision: this file is loaded into every single prompt, not retrieved on demand. The agent starts every conversation already knowing who you are.

Daily logs are OpenClaw’s first implementation of episodic memory. They live at ~/.openclaw/workspace/memory/YYYY-MM-DD.md and contain recent context organized by day. They’re append-only; new entries get added, nothing is removed. Today’s and yesterday’s logs are loaded at the start of each session.

Session snapshots are the second implementation of episodic memory. When you start a new session with /new or /reset, a hook captures the last 15 meaningful messages from your conversation, filtering out tool calls, system messages, and slash commands. It’s not a summary; it’s the raw conversation text, saved as a markdown file with a descriptive name like ~/.openclaw/workspace/memory/2026-02-08-api-design.md.

So at its core, OpenClaw’s memory is markdown files. But the files are only half the story. Without something that reads and writes them at the right time, they’re just sitting there doing nothing.

The files are the filing cabinet. What comes next are the four mechanisms that move things from the desk to the cabinet at the right moments.

How It All Comes Together
Mechanism 1: Bootstrap loading at session start.

For every new conversation, MEMORY.md is automatically injected into the prompt. The agent always has it. On top of that, the agent’s instructions tell it to read today’s and yesterday’s daily logs for recent context. MEMORY.md is injected by the system; the daily logs are loaded by the agent itself, following its own instructions.

This is the simplest pattern and the most important one. The agent doesn’t have to search for context. It’s just there.

Mechanism 2: Pre-compaction flush.

OpenClaw takes a count-based approach to compaction. When a session nears the context window limit, OpenClaw injects a silent agentic turn (invisible to the user) with the following instructions:

“Pre-compaction memory flush. Store durable memories now (use memory/YYYY-MM-DD.md; create memory/ if needed). If nothing to store, reply with NO_REPLY.”

When the agent sees this, it writes anything worth keeping to the daily log, then replies with NO_REPLY so it never surfaces in the conversation.

This turns a destructive operation into a checkpoint. Losing context becomes a save point rather than a loss. It’s the write-ahead log pattern: save before you lose, load when you start. The same pattern databases have used for decades, applied to agent memory.

Mechanism 3: Session snapshot on /new.

When you explicitly start a new session, a hook grabs the last chunk of your conversation, filters to meaningful messages only, and saves it with a descriptive filename. It only fires on explicit /new or /reset; closing the browser doesn’t trigger it. It’s an intentional save point, not an automatic backup.

Mechanism 4: User says “remember this.”

The simplest mechanism. If you ask the agent to remember something, it determines whether it belongs in MEMORY.md as semantic memory or the daily log as episodic memory, and writes accordingly. No special hook needed, just file-writing capabilities and instructions for how to categorize.

Why This Matters Beyond OpenClaw
Claude Code recently shipped a native memory feature. It also uses markdown files. The pattern is becoming standard.

The agents that feel most useful, the ones that stick as part of your workflow, are the ones that remember you. An agent that asks your tech stack every session doesn’t feel like a colleague. An agent that already knows your conventions and what you worked on yesterday does.

The building blocks are the same regardless of what you’re building on: file-first storage, lifecycle triggers tied to meaningful session events, and extraction and consolidation to keep memory clean over time.

Wrapping Up
OpenClaw’s entire memory system comes down to markdown files and knowing when to write to them. Semantic memory in MEMORY.md. Episodic memory in daily logs and session snapshots. And four mechanisms that fire at the right moments in a conversation’s lifecycle.

You don’t need a complex setup to give an agent memory. You need a clear answer to three questions: what’s worth remembering, where does it go, and when does it get written.

Further Reading
How AI Agents Remember Things: The video companion to this post
Context Engineering: Sessions and Memory: Google’s whitepaper on agent memory taxonomy
Understanding Claude Code’s Context Window: How context windows work and how to manage them
How I Use Claude Code: My Complete Development Workflow: Practical patterns for AI-assisted development
More on building real systems