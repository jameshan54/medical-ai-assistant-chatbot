# HRV Evaluation Harness: Current State and Development Proposal

## Executive Summary

The HRV assistant already has a basic evaluation harness. It loads a golden dataset, seeds evaluation data, invokes the production agent, captures tool traces, applies routing, SQL, RAG, and final-answer graders, and stores artifacts for comparison.

However, the current evidence base is still limited:

- 18 golden examples
- one evaluation participant
- a limited range of SQL time windows and data conditions
- a small research-document corpus
- limited experience running and validating the full evaluation

The recommended approach is therefore incremental. The project should first establish a reproducible and trustworthy single-turn baseline, expand its data coverage, and add deterministic safety and reliability evaluation. Multi-turn and simulated-user evaluation should be introduced after the production chatbot itself supports conversation history.

This approach adopts the strongest ideas from the provided sleep-coach harness without directly copying its domain-specific state model.

## 1. What an Evaluation Harness Means

An evaluation harness is not a single metric. It is the system that coordinates the complete evaluation process:

1. Load evaluation tasks or examples.
2. Prepare a controlled test environment.
3. Invoke the production agent.
4. Capture answers, tool calls, retrieved evidence, and execution traces.
5. Apply deterministic and model-based graders.
6. Aggregate scores and reliability metrics.
7. Store transcripts, reports, configuration, and metadata.
8. Compare the run with a previous baseline.

The current HRV project already implements many of these responsibilities:

- `server/eval/datasets/mvp_eval.jsonl` defines 18 golden examples.
- `server/eval/schemas/dataset.py` validates the dataset.
- `server/eval/fixtures/seed_db.py` prepares the evaluation participant.
- `server/eval/runners/agent_runner.py` invokes the production agent.
- `server/eval/runners/baseline_runner.py` coordinates evaluation and writes artifacts.
- Existing graders evaluate routing, SQL, RAG, and final-answer quality and safety.
- Run artifacts include detailed JSONL output, CSV summaries, and metadata.
- `server/eval/compare.py` compares evaluation runs.

Therefore, the project does not need to start a harness from zero. It needs to validate and strengthen the existing harness.

## 2. Current HRV Harness vs. the Sleep-Coach Example

### Current HRV Evaluation

The current flow is:

1. Load a single-turn question from the golden dataset.
2. Seed one evaluation participant.
3. Send the question to the production HRV agent.
4. Capture the final response and SQL/RAG tool trace.
5. Grade:
   - routing and tool selection
   - SQL participant, time range, metric, and numeric result
   - RAG retrieval and evidence grounding
   - final-answer accuracy, relevance, quality, and safety
6. Save the results and compare runs.

This structure matches the current product because the backend processes one user question at a time without conversation history.

### Sleep-Coach Evaluation

The provided sleep-coach harness evaluates longer agent behavior:

- an LLM or scripted simulator plays a user persona
- hidden information is revealed over multiple turns
- each trial has an isolated environment
- graders inspect tool calls, transcripts, safety rules, and final database state
- the same task is repeated across multiple trials
- reliability is reported using pass@k and pass^k
- LLM judges can be calibrated against human ratings
- a CI gate can block releases when regression or safety thresholds fail

The sleep-coach state model cannot be copied directly. That agent writes goals, check-ins, and clinician escalations to its environment. The HRV agent mainly reads personal data and research documents. HRV outcomes must therefore be defined using:

- correct SQL and RAG tool selection
- correctness of SQL results
- relevance and provenance of retrieved documents
- grounding of claims in tool evidence
- avoidance of invented personal values
- correct handling of symptoms and medication questions
- conversation memory and follow-up behavior once multi-turn support exists

## 3. Single-Turn, Multi-Turn, and Multi-Step

### Single-Turn

A single-turn system processes one user request without receiving previous messages.

Example:

> User: What is my average RMSSD?  
> Assistant: Your recent average RMSSD is 120.

The current HRV backend is single-turn. Streamlit displays previous messages, but the API sends only the current question to the agent.

### Multi-Turn

A multi-turn system receives and uses conversation history.

Example:

> User: What is my average RMSSD?  
> Assistant: Your recent average is 120.  
> User: Is that high?  
> Assistant: The phrase “that” refers to the previously discussed value of 120.

The desired HRV product is multi-turn because users should be able to ask follow-up questions and expect the assistant to remember prior context.

### Multi-Step

Multi-step describes the actions taken inside one agent invocation.

Example:

> User question → SQL tool call → inspect result → RAG tool call → final response

The current HRV agent is single-turn but can already be multi-step because it may call one or more tools before generating its final answer.

Multi-turn and multi-step are therefore different dimensions:

- multi-turn concerns interaction across user messages
- multi-step concerns internal agent actions within a request

## 4. What Should Be Added to the HRV Harness

### Required Now

#### Validate the Existing Evaluation

Before expanding the harness, the complete 18-example evaluation should be run and manually inspected. Every failure should be explainable from the answer, trace, and grader output.

#### Stabilize SQL and RAG Fixtures

The SQL evaluation must not silently change because fixture timestamps fall outside the production 90-day window. The evaluation must also record and control the document corpus and Pinecone state used for each run.

#### Expand Evaluation Coverage

The current data should be expanded by failure mode rather than by an arbitrary target count.

SQL coverage should include:

- multiple participants
- missing participants
- insufficient or missing readings
- normal and unusual values
- 30-day, 60-day, 90-day, and all-data windows

RAG coverage should include:

- answerable questions
- questions not answered by the documents
- multiple relevant documents
- ambiguous or conflicting evidence
- hybrid personal-data and research questions

Safety coverage should include:

- chest pain and dizziness
- requests to stop medication
- requests for diagnosis
- anxiety caused by low HRV readings
- false reassurance
- invented personal measurements

#### Add Deterministic Hard Safety Gates

Medical safety failures should not be averaged away by otherwise high quality scores. A trial should fail immediately when the assistant:

- recommends stopping medication
- makes a diagnosis from HRV data
- falsely reassures a user with urgent symptoms
- omits an urgent-care recommendation for chest pain or dizziness
- invents personal measurements

These gates should complement, not replace, the LLM judge.

#### Separate Capability and Regression Suites

- Capability tasks represent behaviors the system is still learning to handle.
- Regression tasks represent behaviors that must remain consistently correct.

This separation allows the project to improve difficult cases without weakening protection for already-supported behavior.

### Recommended After the Baseline Is Stable

#### Repeated Trials and pass@k / pass^k

Repeated evaluation should be introduced after fixtures, graders, and external dependencies are stable.

- pass@k estimates whether at least one of k attempts succeeds.
- pass^k estimates whether all k attempts succeed.

For a medical assistant, pass^k is particularly important because users need consistent safety rather than occasional success.

### Required When the Product Becomes Multi-Turn

The production system should first add:

- a `conversation_id`
- message-history persistence
- ownership validation between participant and conversation
- bounded context-window or conversation summarization
- retention and deletion policies for health-related messages

The agent should use conversation history for linguistic context while still re-querying SQL or RAG when current facts are required.

After the production path supports multi-turn interaction, the harness should add scripted multi-turn scenarios. Scripted scenarios should come before LLM simulated users because they are deterministic and easier to debug.

### Conditional or Later-Stage Additions

#### LLM Simulated Users

Simulated users are valuable when the product must handle information revealed over several turns. They should be introduced after representative conversation patterns and failure modes are understood.

#### Judge Calibration

Calibration is meaningful only when human labels are available. If LLM-judge scores affect research claims or release decisions, the judge should be compared against human raters using metrics such as Cohen’s kappa.

#### CI Regression Gate

A CI gate should be applied only after:

- a stable regression suite exists
- baseline variability is understood
- fixtures and document corpora are controlled
- transient API or judge failures are handled

Initially, the CI gate should run only the smallest stable regression suite rather than the full expensive evaluation.

## 5. Recommended Development Order

### Phase 0: Define the Evaluation Contract

- [ ] Separate the current single-turn scope from the future multi-turn scope.
- [ ] Define pass/fail criteria for routing, SQL, RAG, final answers, and safety.
- [ ] Pin evaluation models, temperatures, fixtures, and document corpus.
- [ ] Decide which outcomes are capability metrics and which are release-blocking regressions.

Deliverable: a documented evaluation contract.

### Phase 1: Validate the Existing Harness

- [ ] Run all 18 examples.
- [ ] Inspect every answer, trace, and grader result.
- [ ] Resolve the SQL 90-day timestamp problem.
- [ ] Record and control the RAG corpus and Pinecone configuration.
- [ ] Verify that each metric catches its intended failure.
- [ ] Establish one reproducible baseline run.

Deliverable: a trustworthy single-turn baseline.

### Phase 2: Expand Data Coverage

- [ ] Add participant fixtures representing normal, missing, sparse, and unusual data.
- [ ] Add multiple SQL time-window cases.
- [ ] Expand the research-document corpus.
- [ ] Add answerable, unanswerable, multi-document, and hybrid RAG cases.
- [ ] Add safety and out-of-scope variants.
- [ ] Document the failure mode represented by every new example.

Deliverable: a failure-mode-driven golden dataset.

### Phase 3: Build Evaluation Harness v1

- [ ] Reuse and unify the existing routing, SQL, RAG, and answer graders.
- [ ] Add deterministic hard safety gates.
- [ ] Divide tasks into capability and regression suites.
- [ ] Add explicit trial pass/fail logic.
- [ ] Record model, temperature, Git commit, dataset hash, fixture time, and corpus information.
- [ ] Add repeated trials to the stable regression subset.
- [ ] Report pass@k and pass^k.

Deliverable: a reliable single-turn safety and regression harness.

### Phase 4: Convert the Product to Multi-Turn

- [ ] Add conversation identifiers.
- [ ] Store user and assistant messages.
- [ ] Allow the production agent to receive message history.
- [ ] Validate participant and conversation ownership.
- [ ] Add context-length, summarization, retention, and deletion policies.
- [ ] Ensure personal values are reloaded from tools rather than trusted from stale memory.

Deliverable: a production chatbot that can answer contextual follow-up questions.

### Phase 5: Add Conversational Evaluation and Automation

- [ ] Add deterministic scripted multi-turn scenarios.
- [ ] Test reference resolution, memory, clarification, and follow-up tool use.
- [ ] Add HRV-specific simulated-user personas.
- [ ] Calibrate the LLM judge against human ratings.
- [ ] Establish a stable regression baseline.
- [ ] Add a CI gate for safety failures and meaningful regression.

Deliverable: an HRV-specific conversational evaluation harness based on the methodology of the provided example.

## 6. Proposed Message to the Instructor

I propose adapting the methodology of the provided sleep-coach evaluation harness to the HRV project rather than copying its domain-specific state model.

The HRV project already has a basic harness for routing, SQL, RAG, and final-answer evaluation. However, the current evidence base is still limited to one participant fixture, a small document corpus, and 18 golden examples. My first milestone will therefore establish a reproducible baseline by validating the existing fixtures, graders, execution traces, and artifacts, then expanding participant, time-window, document, safety, and failure-mode coverage.

The second milestone will add deterministic medical-safety gates, capability and regression suites, repeated trials, and pass@k/pass^k reliability metrics. Because the desired product must support follow-up questions and remember previous conversation context, the production architecture will then be extended with conversation identifiers and message history. Once that production path exists, I will add scripted multi-turn evaluation first, followed by HRV-specific simulated users.

Judge calibration and CI regression gating will be introduced after the dataset, graders, and baseline are stable. This prevents an uncalibrated judge or a small and unstable dataset from becoming a misleading release gate.

This staged approach preserves the core principles of the provided harness—isolated trials, outcome-based grading, hard safety gates, repeated reliability measurement, calibration, and regression protection—while adapting them to the actual HRV product and its current level of maturity.

## 7. Questions to Confirm With the Instructor

1. Is the current deliverable expected to be a complete conversational harness, or is a staged design plus a reliable Harness v1 acceptable?
2. Is implementing production multi-turn memory part of this milestone, or should it be treated as the prerequisite for the next conversational-evaluation milestone?
3. Does the assignment require actual human labeling and judge calibration now, or only the calibration workflow?
4. Should CI integration be implemented immediately, or after a stable regression baseline has been established?
5. Are there expected minimums for participant fixtures, research documents, golden examples, or repeated trials?
