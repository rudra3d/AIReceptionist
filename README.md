# AI Receptionist

A high-fidelity, open-source AI phone receptionist powered by OpenAI's Realtime API and LiveKit.

Unlike existing AI receptionist products that use cheap cascaded STT-LLM-TTS pipelines, this project uses OpenAI's speech-to-speech model for natural, low-latency conversations that sound like a real person.

## Features

- Natural speech-to-speech conversations via OpenAI Realtime API
- Inbound phone call handling via SIP/Twilio/Telnyx
- FAQ answering from configurable knowledge base
- Call transfers to departments/people
- Message taking with file-based storage
- Multi-business support from a single agent
- Built-in noise cancellation for phone audio

## Prerequisites

- Python 3.11+
- OpenAI API key (with Realtime API access)
- LiveKit server ([self-hosted](https://docs.livekit.io/home/self-hosting/local/) or [LiveKit Cloud](https://cloud.livekit.io))
- SIP trunk provider (Twilio or Telnyx) with a phone number

## Quick Start

1. **Clone and install:**

```bash
git clone https://github.com/yourusername/AIReceptionist.git
cd AIReceptionist
pip install -e .
```

2. **Configure environment:**

```bash
cp .env.example .env
# Edit .env with your keys:
#   LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, OPENAI_API_KEY
```

3. **Configure your business:**

```bash
cp config/businesses/example-dental.yaml config/businesses/my-business.yaml
# Edit with your business name, FAQs, routing numbers, hours
```

4. **Set up telephony:**

Follow the [LiveKit SIP Trunk Setup Guide](https://docs.livekit.io/telephony/start/sip-trunk-setup/) to:
- Create an inbound SIP trunk pointing to your Twilio/Telnyx number
- Create a dispatch rule to route calls to the `receptionist` agent

5. **Run:**

```bash
python -m receptionist.agent dev
```

Call your phone number — you should hear your receptionist greeting.

## Configuration

Each business is defined by a YAML file in `config/businesses/`. See `example-dental.yaml` for a complete example.

Key sections:
- `business` — name, type, timezone
- `voice` — OpenAI voice selection (coral, alloy, ash, ballad, echo, sage, shimmer, verse)
- `greeting` — what the receptionist says when answering
- `personality` — system prompt personality instructions
- `hours` — business hours per day of week
- `routing` — departments/people the receptionist can transfer to
- `faqs` — question/answer pairs the receptionist can answer
- `messages` — how to store messages (file or webhook)

## Multi-Business Setup

One running agent can serve multiple businesses. Each inbound phone number maps to a business config via SIP dispatch rule metadata:

```json
{
  "metadata": "{\"config\": \"my-business\"}"
}
```

This loads `config/businesses/my-business.yaml`.

## Cost

Using OpenAI Realtime API: ~$0.20-0.30/min per call. A dental office with 30 calls/day averaging 2 minutes costs roughly $15/day.

## License

MIT
