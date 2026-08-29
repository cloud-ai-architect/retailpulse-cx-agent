# ADR-0009: Use Amazon Polly for voice synthesis (TTS) in Phase 1; evaluate LiveKit for Phase 2

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: voice, ux, cost

## Context and problem statement

RetailPulse needs a voice channel. Customers will call in (or use a web voice widget) and talk to the agent. We need:

- Speech-to-text (STT) for the customer's voice
- Text-to-speech (TTS) for the agent's response
- Low latency (< 2s for natural conversation)
- Cost-effective for portfolio demo volume

## Decision drivers

- Low latency for natural conversation
- AWS-native preferred (no third-party billing)
- Easy to integrate with Step Function
- Good quality voices (English + Indian accents for India market)
- Cost: < $5/month for portfolio demo volume

## Considered options

### Option 1: Amazon Polly (chosen for Phase 1)

- ✅ AWS-native, integrated with Step Functions
- ✅ $4 per million characters (neural voices)
- ✅ Good English and Indian (English-IN) voices: Kajal, Aditi
- ✅ SSML support for emphasis, pauses
- ⚠️ One-way TTS only (need separate STT)

### Option 2: Amazon Transcribe + Polly

- ✅ Full pipeline in AWS
- ✅ Transcribe: $1.44/hour of audio
- ⚠️ STT is a separate service to integrate

### Option 3: LiveKit

- ✅ Real-time WebRTC
- ✅ Open source agents framework
- ❌ More complex infra
- ❌ Additional cost

### Option 4: OpenAI Whisper + TTS

- ✅ High quality
- ❌ External API, per-call cost
- ❌ Data leaves AWS

## Decision outcome

**Chosen: Amazon Polly for TTS + Amazon Transcribe for STT** in Phase 1. **LiveKit evaluated for Phase 2** if real-time WebRTC is needed.

Voice flow:

1. Customer audio → Transcribe (Lambda) → text
2. Text → CrewAI agents (orchestrator) → response text
3. Response text → Polly (Lambda) → audio response

### Consequences

**Positive**

- AWS-native, predictable cost
- No third-party dependencies
- High-quality voices including Indian
- Easy to scale

**Negative**

- Two-step STT → agent → TTS adds latency (~2s)
- Polly voices are not as natural as latest OpenAI/ElevenLabs

### Confirmation

- p95 voice-to-voice latency < 4s
- Voice transcription accuracy > 95% on common phrases
- Cost < $2/month at demo volume (100 conversations × 5 min × $0.0001/min)

## Pros and cons of the options

| Option | Latency | Cost | AWS-native | Quality |
|---|---|---|---|---|
| **Polly + Transcribe** | ⚠️ ~2s | ✅ $4/1M chars | ✅ | ✅ Good |
| LiveKit | ✅ <500ms | ⚠️ $0.004/min | ❌ | ✅ Excellent |
| OpenAI Realtime | ✅ <500ms | ❌ $0.06/min | ❌ | ✅ Excellent |

## References

- [Amazon Polly](https://aws.amazon.com/polly/)
- [Amazon Transcribe](https://aws.amazon.com/transcribe/)
- [LiveKit](https://livekit.io/)
- [Polly pricing](https://aws.amazon.com/polly/pricing/)
