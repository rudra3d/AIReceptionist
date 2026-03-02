# Architecture

This document describes the end-to-end architecture of AI Receptionist: how a phone call flows through the system, what each component does, how the modules interact, and the design decisions behind it all.

---

## Table of Contents

- [System Overview](#system-overview)
- [Call Flow](#call-flow)
- [Component Diagram](#component-diagram)
- [Module Responsibilities](#module-responsibilities)
  - [agent.py — Core Agent Logic](#agentpy--core-agent-logic)
  - [config.py — Configuration Models](#configpy--configuration-models)
  - [prompts.py — System Prompt Builder](#promptspy--system-prompt-builder)
  - [messages.py — Message Persistence](#messagespy--message-persistence)
- [Data Flow](#data-flow)
- [Configuration Architecture](#configuration-architecture)
- [Security Model](#security-model)
- [Design Decisions](#design-decisions)
- [Future Architecture](#future-architecture)

---

## System Overview

```
                    ┌──────────────┐
   PSTN Call ──────►│  SIP Trunk   │
   (Caller)        │ Twilio/Telnyx│
                    └──────┬───────┘
                           │ SIP/RTP
                           ▼
                    ┌──────────────┐
                    │   LiveKit    │
                    │   Server     │
                    │  (SFU/SIP)  │
                    └──────┬───────┘
                           │ WebRTC
                           ▼
                    ┌──────────────────────────────────┐
                    │      LiveKit Agent (Python)       │
                    │                                    │
                    │  ┌─────────────────────────────┐  │
                    │  │    Noise Cancellation        │  │
                    │  │  BVCTelephony (SIP calls)    │  │
                    │  │  BVC (WebRTC calls)          │  │
                    │  └─────────────┬───────────────┘  │
                    │                │                    │
                    │  ┌─────────────▼───────────────┐  │
                    │  │   OpenAI Realtime API        │  │
                    │  │   (Speech-to-Speech Model)   │  │
                    │  │   Voice: configurable        │  │
                    │  └─────────────┬───────────────┘  │
                    │                │                    │
                    │  ┌─────────────▼───────────────┐  │
                    │  │   Receptionist Agent         │  │
                    │  │   - Config-driven behavior   │  │
                    │  │   - FAQ lookup               │  │
                    │  │   - Call transfer             │  │
                    │  │   - Message taking            │  │
                    │  │   - Hours checking            │  │
                    │  └─────────────────────────────┘  │
                    └──────────────────────────────────┘
```

The system follows a linear pipeline: PSTN calls arrive via a SIP trunk, are bridged into LiveKit as WebRTC sessions, processed through noise cancellation, handled by the OpenAI Realtime API for speech understanding and generation, and orchestrated by the Receptionist agent which executes business logic based on YAML configuration.

---

## Call Flow

### 1. Inbound Call Arrives

A caller dials the business phone number. The SIP trunk provider (Twilio or Telnyx) receives the call and forwards it to the LiveKit server via SIP.

### 2. LiveKit Creates a Room

LiveKit server creates a room for the call and dispatches the session to a registered agent worker. The room contains the SIP participant (the caller).

### 3. Agent Session Starts (`handle_call`)

The `@server.rtc_session()` decorator in `agent.py` triggers `handle_call()`:

```
handle_call(ctx: rtc.JobContext)
    ├── load_business_config(ctx)     # Determine which business config to use
    │   ├── Check job metadata for "config" key
    │   ├── Validate slug (path traversal protection)
    │   └── Fall back to first YAML in config/businesses/
    │
    ├── Build system prompt
    │   └── prompts.build_system_prompt(config)
    │
    ├── Create AgentSession
    │   ├── RealtimeModel (OpenAI, voice from config)
    │   └── Noise cancellation (BVCTelephony for SIP, BVC for WebRTC)
    │
    └── Start agent in room
        └── agent.start(ctx.room)
```

### 4. Conversation Loop

Once started, the OpenAI Realtime API handles the conversation in a continuous speech-to-speech loop:

1. Caller speaks into their phone.
2. Audio flows through the SIP trunk into LiveKit.
3. Noise cancellation cleans the audio.
4. OpenAI Realtime API receives the audio, understands intent, and generates a spoken response.
5. When the model decides a tool call is needed, it invokes one of the four function tools.
6. The agent executes the tool and returns the result to the model.
7. The model incorporates the result into its spoken response.

### 5. Function Tool Execution

The agent exposes four tools to the model:

| Tool | Trigger | Effect |
|------|---------|--------|
| `lookup_faq` | Caller asks a question | Searches configured FAQs, returns answer |
| `transfer_call` | Caller requests a department | Initiates SIP transfer via LiveKit API |
| `take_message` | Caller wants to leave a message | Saves message to file or webhook |
| `get_business_hours` | Caller asks about hours | Returns current open/closed status with schedule |

### 6. Call Ends

When the caller hangs up, the SIP session terminates, LiveKit closes the room, and the agent session is cleaned up.

---

## Module Responsibilities

### agent.py — Core Agent Logic

This is the entry point and orchestrator. It contains:

- **`AgentServer`**: A LiveKit `agents.Worker` (configured via the `cli` module) that listens for incoming sessions.
- **`handle_call(ctx)`**: The session handler decorated with `@server.rtc_session()`. Loads configuration, builds the prompt, initializes the AI model, and starts the agent.
- **`load_business_config(ctx)`**: Resolves which YAML config to use based on job metadata. Implements path traversal protection by validating the config slug against `^[a-zA-Z0-9_-]+$`.
- **`Receptionist(Agent)`**: Subclass of `agents.Agent`. Contains:
  - `on_enter()` — Called when the agent enters the conversation; delivers the greeting.
  - `lookup_faq(question)` — Function tool for FAQ matching.
  - `transfer_call(department)` — Function tool for SIP call transfer.
  - `take_message(caller_name, message, callback_number)` — Function tool for message persistence.
  - `get_business_hours()` — Function tool for timezone-aware hours checking.
  - `_get_caller_identity()` — Helper to find the SIP participant in the room.

**Entry point**: `python -m receptionist.agent dev` starts the agent in development mode.

### config.py — Configuration Models

Pydantic models that define and validate the YAML configuration:

| Model | Fields | Validation |
|-------|--------|------------|
| `BusinessInfo` | name, type, timezone | Basic string validation |
| `VoiceConfig` | voice_id (default: "coral") | Must be valid OpenAI voice |
| `DayHours` | open, close | HH:MM format validation |
| `WeeklyHours` | monday through sunday | Each day is DayHours or None ("closed") |
| `RoutingEntry` | name, number, description | Non-empty strings |
| `FAQEntry` | question, answer | Non-empty strings |
| `DeliveryMethod` | Literal["file", "webhook"] | Enum-like |
| `MessagesConfig` | delivery, file_path, webhook_url | Cross-field: file requires file_path, webhook requires webhook_url |
| `BusinessConfig` | All of the above, plus greeting, personality, after_hours_message, routing, faqs | Top-level model with `from_yaml_string()` classmethod |

**`load_config(path)`**: Reads a YAML file with UTF-8 encoding and returns a validated `BusinessConfig`.

### prompts.py — System Prompt Builder

**`build_system_prompt(config)`** constructs a comprehensive LLM system prompt from the `BusinessConfig`. The prompt includes:

1. **Business identity** — name, type, role definition.
2. **Personality instructions** — tone, style, behavior from the personality field.
3. **Hours schedule** — formatted weekly schedule with open/close times per day.
4. **After-hours message** — what to say when the business is closed.
5. **Routing departments** — available transfer targets with descriptions.
6. **Tool usage instructions** — when and how to use each function tool.
7. **FAQ knowledge** — question-answer pairs embedded in the prompt.
8. **Behavioral rules** — constraints on the agent's behavior (stay in role, be concise, etc.).

### messages.py — Message Persistence

- **`Message`** dataclass: `caller_name`, `callback_number`, `message`, `business_name`, `timestamp` (auto-set to UTC).
- **`save_message(message, config)`**: Dispatches to the appropriate delivery backend based on `config.messages.delivery`.
- **`_save_to_file(message, path)`**: Writes JSON files with microsecond-precision timestamps (e.g., `message_20260302_143025_123456.json`).
- **`_send_webhook(message, url)`**: Currently raises `NotImplementedError` (planned for future implementation).

---

## Data Flow

```
                YAML Config
                    │
                    ▼
            ┌───────────────┐
            │   config.py   │──── Validated BusinessConfig
            └───────┬───────┘
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │prompts.py│ │ agent.py │ │messages. │
    │          │ │          │ │   py     │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │
         ▼            ▼            ▼
    System Prompt  Tool Logic   File/Webhook
```

1. A YAML configuration file is loaded and validated through Pydantic models in `config.py`.
2. The validated `BusinessConfig` flows into three consumers:
   - `prompts.py` uses it to build the system prompt.
   - `agent.py` uses it to configure tools and agent behavior.
   - `messages.py` uses it to determine message delivery settings.

---

## Configuration Architecture

Configuration follows a layered approach:

### Layer 1: Environment Variables (`.env`)

Infrastructure credentials that are shared across all businesses:

```
LIVEKIT_URL=wss://your-instance.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=sk-your-openai-key
```

### Layer 2: Business Configuration (YAML)

Per-business settings that define the receptionist's behavior. Stored in `config/businesses/`. Each file is a complete, self-contained definition of one business's receptionist.

### Layer 3: Job Metadata (Runtime)

When a call arrives, LiveKit job metadata specifies which business config to load. This enables multi-business support from a single deployment. See [Multi-Business Setup](multi-business-setup.md).

---

## Security Model

### Path Traversal Protection

Config slug names from job metadata are validated against `^[a-zA-Z0-9_-]+$` before being used in file paths. This prevents directory traversal attacks (e.g., `../../etc/passwd`).

### Input Validation

- All YAML configs are loaded with `yaml.safe_load()` to prevent arbitrary code execution.
- Pydantic models enforce type and format validation on all config fields.
- HH:MM time formats are validated with regex patterns.
- Cross-field validation ensures consistency (e.g., file delivery requires file_path).

### Error Sanitization

When function tools encounter errors (e.g., SIP transfer fails), the error messages returned to the LLM are sanitized to avoid leaking internal details to callers.

### Async I/O Safety

File operations in message saving use `asyncio.to_thread()` to avoid blocking the event loop, which is critical for maintaining call quality.

---

## Design Decisions

### Why OpenAI Realtime API (Speech-to-Speech)?

The Realtime API provides a single model that handles both speech understanding and generation. This eliminates the latency of a traditional STT-to-LLM-to-TTS pipeline and produces more natural-sounding conversations with better prosody, intonation, and turn-taking.

### Why LiveKit?

LiveKit provides production-grade WebRTC infrastructure with built-in SIP support, agent lifecycle management, and noise cancellation. Its Agents SDK offers a clean Python API for building voice AI applications without managing low-level WebRTC or SIP details.

### Why YAML Configuration?

YAML is human-readable, widely understood, and suitable for structured configuration. It allows business owners or system administrators to customize the receptionist without touching code. Pydantic validation ensures that configuration errors are caught at load time with clear error messages.

### Why Pydantic for Config Models?

Pydantic provides automatic type validation, clear error messages, and serialization/deserialization. It catches configuration errors early (at startup, not mid-call) and provides IDE support through type hints.

### Why File-Based Message Storage?

File-based storage was chosen for the initial implementation because it has zero dependencies, works everywhere, and is simple to debug. Webhook delivery is architected but not yet implemented, providing a clear path to integration with CRMs, email systems, and notification services.

### Why Noise Cancellation?

Phone calls are inherently noisy (background noise, speakerphone, car environments). LiveKit's noise cancellation plugin significantly improves speech recognition accuracy. The system uses `BVCTelephony` for SIP calls (optimized for telephony audio characteristics) and `BVC` for WebRTC calls.

---

## Future Architecture

Planned architectural changes and additions:

### Call Recordings (LiveKit Egress)

LiveKit Egress can record calls for compliance, quality assurance, and training. This would add a recording component that captures the full audio stream.

### Transcripts

Post-call transcription would provide searchable text records of every conversation, useful for analytics and dispute resolution.

### Email Notifications

Integration with email services (SendGrid, SES) to notify business owners of messages, missed calls, and daily summaries.

### Cascaded Pipeline Mode

An alternative to the Realtime API that uses separate components:
- **Deepgram** for speech-to-text
- **Claude** for language understanding and generation
- **ElevenLabs** for text-to-speech

This provides more control over each stage and potentially lower costs for high-volume deployments.

### Web Widget

A browser-based calling widget that allows website visitors to speak with the receptionist without a phone call, using WebRTC directly.

### Admin Dashboard

A web interface for managing business configurations, viewing call history, reading messages, and monitoring system health.
