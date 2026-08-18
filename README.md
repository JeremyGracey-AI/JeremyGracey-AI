# Jeremy Gracey
 
[jeremygracey.ai](https://jeremygracey.ai) · [LinkedIn](https://www.linkedin.com/in/jeremygracey-ai/) · [Hugging Face](https://huggingface.co/jeremygracey-ai) · [jeremy.a.gracey@gmail.com](mailto:jeremy.a.gracey@gmail.com)  ·  gracey.ai@outlook.com
 
AI/ML engineer and technical founder in Seattle. I build agent systems that hold up under audit: pipelines that log their decisions, memory with governance and replay, RAG that cites the exact page behind every claim.
 
Before software I worked emergency medicine, acute psychiatric care, and special education. Nobody in those rooms accepts "trust me" as an answer, and I never learned to accept it from software either. Everything below is built to that standard.
 
## What I build
 
Five threads, each with public code behind it.
 
**Agent infrastructure.** The plumbing that makes autonomous agents accountable. [Compass BlackBox IQ](https://github.com/JeremyGracey-AI/Agents-League-Hackathon-Compass-BlackBox-IQ) is a flight recorder for agents: git-backed memory, decision records, and a skill forge, exposed over MCP. [llm-council-mcp](https://github.com/JeremyGracey-AI/llm-council-mcp) runs multi-model deliberation as an MCP server for Claude Code — ships on PyPI as `mcp-llm-council`.
 
**Agent governance.** [governance-drift-researcher](https://github.com/JeremyGracey-AI/governance-drift-researcher) detects drift in an AI-agent estate: every finding carries verifiable evidence, findings that can't be re-verified are dropped, and nothing publishes without human sign-off. [Run it live on WeaveMind Cloud](https://app.weavemind.ai/app#/p/gracey_dev/governance-drift-researcher-v2) for about $0.03, or `pip install governance-drift`. [guss](https://github.com/JeremyGracey-AI/guss) is the same philosophy on 7 watts — a Jetson-hosted agent that monitors itself, heals itself, paper-trades against a benchmark, and publishes its own dashboard.
 
**Compilers and GPU performance.** [triton-kernel-lab](https://github.com/JeremyGracey-AI/triton-kernel-lab) is hand-written Triton kernels with honest benchmarks on a Jetson Orin Nano, plus a working study of LLVM, MLIR, and TorchDynamo/Inductor.
 
**Neurotech and edge hardware.** [nexus-neuromirror](https://github.com/JeremyGracey-AI/nexus-neuromirror) is offline-first EEG neurofeedback for the Mind Media NeXus-10, from EDF verification to a live dashboard. `pip install nexus-neuromirror`.
 
**Clinical AI on open standards.** [clinical-ai-agent](https://github.com/JeremyGracey-AI/clinical-ai-agent) is citation-traceable decision support on SMART on FHIR: a five-agent pipeline with dual citations back to patient data and clinical sources. [Hospital-Readmission-Prediction-Model](https://github.com/JeremyGracey-AI/Hospital-Readmission-Prediction-Model) covers the classical ML side, synthetic EHR data through SHAP-based clinical interpretation.
 
Off GitHub: [PREVERA GUARDIAN+AI](https://preveraguard.com), fall-risk detection built on V-JEPA and LIDAR on Jetson hardware (USPTO provisional filed 2026), and customer-facing agents for real businesses — booking, triage, and operations — deployed and in use.
 
## Beyond the pins
 
The pins are the front door. These hold up past the first click too.
 
- [provenance](https://github.com/JeremyGracey-AI/provenance) — RAG over textbook page images that verifies every claim against the exact page that proves it. Cohere Embed v4 retrieval, Claude vision answers.
- [calibrated-readiness](https://github.com/JeremyGracey-AI/calibrated-readiness) — multi-agent exam-readiness scoring with a 60-second reliability-diagram check. Microsoft Foundry Agent Framework + Foundry IQ.
- [rag-healthcare-ai](https://github.com/JeremyGracey-AI/rag-healthcare-ai) — fully local medical Q&A over the Merck Manual: Mistral-7B on llama.cpp, ChromaDB, no API in the loop.
- [healthcare-vjepa2-agent](https://github.com/JeremyGracey-AI/healthcare-vjepa2-agent) — V-JEPA 2 and Claude reading medical procedure videos and generating teaching material: step breakdowns, narration, quizzes, safety notes.
 
Classical ML lives in [helmnet](https://github.com/JeremyGracey-AI/helmnet) — VGG-16 transfer learning with thresholds tuned for zero-harm deployment — and [renewind-predictive-maintenance](https://github.com/JeremyGracey-AI/renewind-predictive-maintenance), seven Keras architectures against imbalanced turbine sensor data.
 
## Now
 
Consulting through the Claude Partner Network. Digging into what neuropsychology's models of memory can teach agent memory design. Open to applied-AI and systems roles in Seattle or SF.
