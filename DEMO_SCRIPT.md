# ZentroMart VoiceOps — 2-Minute Demonstration Script

**Format**: Timed Audio-Visual Presentation & Pipeline Walkthrough  
**Target Duration**: Exactly 2:00 (120 seconds)  
**Presenter**: Lead Agent Developer  
**Live Connectivity Status Note**: In this submission environment, external live API credentials (`GNANI_API_KEY`, `GROQ_API_KEY`) were not provisioned. Accordingly, speech transcription and synthesis steps below are presented as **verified pipeline demonstrations using deterministic offline runners and mocked SDK endpoints**. No unverified live external calls are claimed.

---

## Demonstration Timeline & Script

| Timestamp | Segment | Visual / System State | Spoken Narration (Speaker) |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:20** | **Problem Statement & Introduction** | Title Slide: *ZentroMart VoiceOps* showing architecture diagram (Gnani STT → RAG / Tools → Gnani TTS). | *"Hello! In high-volume e-commerce customer support, agents face two persistent bottlenecks: handling complex, multi-version return policies accurately, and securely protecting customer order data. Today, we are presenting ZentroMart VoiceOps—an automated customer support agent combining Gnani.ai voice intelligence, grounded FAISS vector retrieval, and zero-trust identity verification gates."* |
| **0:20 – 0:40** | **Customer Query & Gnani STT Transcription** | Terminal execution: `python run_audio.py --input-dir samples/demo --output-dir outputs/demo`<br>Shows simulated audio playback of customer inquiry: `"What is the return window for clothing, and how fast are wallet refunds?"` | *(Planned/Simulated Audio)*: Customer asks question in Indian English.<br><br>*"The customer submits an audio query. ZentroMart's voice runner receives the audio and passes it to the Gnani STT client configured for Indian English (`en-IN`). The audio is transcribed accurately: 'What is the return window for clothing, and how fast are wallet refunds?'"* |
| **0:40 – 1:10** | **Agent Reasoning, RAG Evidence & Response** | Terminal output displays JSON evidence block:<br>• Sources: `RET-9`, `RET-4`<br>• Policy version: `v4`<br>• Decision: `answer`<br>• Answer text displayed on screen. | *"Next, our conversation manager resolves context and queries the FAISS vector index across 21 Markdown knowledge documents. Notice that it retrieves active Version 4 of the Returns policy, citing section `[RET-9]` for clothing exchanges and `[RET-4]` for instant ZentroMart wallet refunds.<br><br>The agent synthesizes the response strictly anchored to these citations: 'Exchanges for clothing are available within the return window under policy RET-9, and wallet refunds are credited instantly under policy RET-4.'"* |
| **1:10 – 1:30** | **Gnani TTS Spoken Output & Security Gating** | Audio playback of synthesized `.wav` using Gnani `Kaveri` voice.<br>Sidebar displays security gate diagram (`phone_suffix` check). | *(Mocked/Offline Synthesized Speech)*: Kaveri voice speaks the verified response smoothly.<br><br>*"The response text is delivered back to the customer via Gnani TTS using the Kaveri voice and timbre-v2.5 model. If the customer asks for private order details, the agent's zero-trust security gate engages: no tracking information is disclosed until the customer confirms their registered phone number's last 4 digits."* |
| **1:30 – 1:50** | **Key Evaluation Results & Benchmark Pass** | Slide displaying `evaluate_agent.py` results table:<br>• 12/12 Benchmark Cases (100%)<br>• 27 Automated Unit Tests (100%)<br>• 0 Verification Security Violations<br>• 82.29% Decision Accuracy | *"To evaluate reliability, we executed a rigorous regression suite: 27 automated tests passed at 100%. Across 96 multi-turn customer turns in our practice benchmark, the agent achieved 82.3% decision accuracy and zero security verification leaks, safely gating protected order data across every single test turn."* |
| **1:50 – 2:00** | **Principal Limitation & Conclusion** | Slide showing Final Status: **READY WITH LIMITATIONS** (Live credentials unverified; Mocked pipeline 100% verified). | *"Our principal limitation is that live production API connectivity remains unverified in this test sandbox due to absent external API keys. With keys provided in `.env`, the pipeline is fully architected for immediate deployment. Thank you!"* |

---

## Demo Checklist for Presenter

- [x] Script adheres strictly to 120-second (2-minute) execution ceiling.
- [x] Includes problem statement, audio input, STT, grounded response, TTS, and security gating.
- [x] Discloses mocked / unverified live status transparently without claiming untested network calls.
- [x] Cites verified evaluation metrics (27 unit tests, 12/12 benchmark cases, 0 verification leaks).
