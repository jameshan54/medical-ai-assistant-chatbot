# HRV Evaluation Harness 현황 및 개발 로드맵

## 핵심 결론

교수님이 제공한 `sleep_coach_evals`를 그대로 복사하기보다는 핵심 평가 방법론을 HRV 프로젝트에 맞게 적용하는 것이 적절하다.

현재 우선순위는 기능을 한꺼번에 추가하는 것이 아니라 다음과 같다.

1. 기존 evaluation을 실제로 실행하고 검증한다.
2. SQL fixture, RAG corpus, golden dataset을 안정화하고 확장한다.
3. hard safety gate와 capability/regression suite를 추가한다.
4. 안정된 평가에 repeated trials와 pass@k/pass^k를 적용한다.
5. 실제 제품을 multi-turn으로 전환한다.
6. 그 후 scripted multi-turn evaluation과 simulated users를 추가한다.
7. 충분한 baseline과 사람 평가가 확보된 뒤 judge calibration과 CI gate를 적용한다.

---

## 1. Evaluation Harness란?

Evaluation harness는 단일 metric이 아니라 평가 전 과정을 반복 가능하게 실행하는 시스템이다.

```text
평가 데이터 로드
    ↓
테스트 환경 및 fixture 준비
    ↓
프로덕션 agent 실행
    ↓
답변·도구 호출·trace 수집
    ↓
grader별 채점
    ↓
점수와 신뢰도 집계
    ↓
transcript·report·metadata 저장
    ↓
이전 baseline과 비교
```

일반적인 evaluation harness의 구성 요소:

- Dataset 또는 task definitions
- Evaluation fixtures 및 격리된 환경
- Production agent runner 또는 adapter
- Tool-call 및 execution trace
- Deterministic graders
- LLM-as-a-judge
- Metric aggregation
- Evaluation artifacts
- Baseline comparison
- Regression gate

---

## 2. 현재 HRV Evaluation Harness

### 현재 실행 흐름

1. `server/eval/datasets/mvp_eval.jsonl`에서 평가 예시를 로드한다.
2. `EvalExample` schema로 데이터를 검증한다.
3. `EVAL_P001` participant 데이터를 seed한다.
4. 실제 production HRV agent를 호출한다.
5. 최종 답변과 SQL/RAG tool trace를 수집한다.
6. routing, SQL, RAG, final-answer grader를 실행한다.
7. `details.jsonl`, `summary.csv`, `metadata.json`을 저장한다.
8. 두 evaluation run을 비교한다.

따라서 현재 프로젝트는 metric 네 개만 존재하는 것이 아니라 dataset, fixture, runner, trace, grader, artifact, comparison을 가진 기본 harness를 이미 갖추고 있다.

### 현재 평가 영역

#### Routing

- 필요한 도구를 정확하게 선택했는지 평가
- `query_hrv_data`
- `search_research_docs`
- 도구가 필요 없는 질문

#### SQL

- 올바른 participant를 조회했는지 평가
- 올바른 기간을 사용했는지 평가
- 요청한 HRV metric을 반환했는지 평가
- 실제 numeric result가 expected result와 일치하는지 평가

#### RAG

- 적절한 연구 문서를 검색했는지 평가
- 답변이 검색 결과에 충실한지 평가
- 질문에 관련된 답변인지 평가
- source와 context가 적절한지 평가

#### Final Answer

- 개인 데이터 정확성
- 연구 근거성
- 질문 관련성
- 의료 안전성
- 전반적인 답변 품질

### 현재 한계

- Golden dataset이 18개뿐이다.
- SQL participant가 한 명뿐이다.
- SQL 기간과 데이터 상태가 다양하지 않다.
- Fixture timestamp가 production의 90일 cutoff 밖으로 벗어날 수 있다.
- RAG document corpus가 작고 다양성이 낮다.
- 전체 evaluation을 충분히 반복 실행하고 수동 검증하지 못했다.
- 의료 안전성이 주로 LLM judge 점수에 의존한다.
- 동일 task를 반복했을 때의 일관성을 측정하지 않는다.
- 현재 backend는 conversation history를 agent에 전달하지 않는다.

---

## 3. 교수님이 제공한 Sleep-Coach Harness

### 주요 구조

- Simulated user가 persona와 hidden goal을 가지고 대화한다.
- 사용자가 정보를 여러 turn에 걸쳐 공개한다.
- 각 trial은 독립된 환경에서 실행된다.
- Agent가 실제로 기록한 DB state를 검사한다.
- Required/forbidden tool calls를 평가한다.
- Transcript와 최대 turn 수를 평가한다.
- 의료 안전 규칙을 hard gate로 검사한다.
- 개인화·근거성·말투 등을 LLM rubric으로 평가한다.
- 같은 task를 여러 번 반복한다.
- pass@k와 pass^k를 계산한다.
- Human labels로 LLM judge를 calibration할 수 있다.
- Regression 결과가 나빠지면 CI에서 release를 차단할 수 있다.

### HRV 프로젝트에 그대로 복사할 수 없는 이유

Sleep-coach agent는 다음과 같은 상태 변경 도구를 사용한다.

- Goal 저장
- Check-in 예약
- Clinician escalation 기록

현재 HRV agent는 주로 읽기 작업을 수행한다.

- Personal HRV SQL 조회
- Research document 검색

따라서 HRV의 outcome은 다음과 같이 다시 정의해야 한다.

- 올바른 SQL/RAG 도구를 사용했는가?
- SQL 결과가 정확한가?
- 검색한 문서가 질문과 관련 있는가?
- 답변의 주장이 tool evidence에 근거하는가?
- 존재하지 않는 개인 수치를 만들지 않았는가?
- 증상과 약물 질문에 안전하게 대응했는가?
- Multi-turn 전환 후 이전 맥락과 후속 질문을 올바르게 처리했는가?

---

## 4. 현재 HRV Harness와 Sleep-Coach 방식 비교

| 구분 | 현재 HRV Harness | Sleep-Coach 방식 |
|---|---|---|
| 평가 대상 | 한 번의 질문과 최종 응답 | 여러 turn의 agent 행동과 최종 outcome |
| 입력 | 18개 JSONL golden examples | Persona, hidden goal, reveal rules가 포함된 task |
| Agent 호출 | 질문 하나로 production agent 호출 | Trial별 conversation history로 반복 호출 |
| 환경 | Evaluation participant와 외부 RAG corpus | Trial마다 독립된 sandbox DB |
| Grader | Routing, SQL, RAG, final-answer | State, tool, transcript, safety gate, LLM rubric |
| 반복 | Example당 기본 1회 | Task당 여러 trial |
| 신뢰도 | 평균 및 pass rate 중심 | pass@k, pass^k, bootstrap CI |
| 안전 | 주로 LLM judge | Deterministic hard gate + LLM rubric |
| 보정 | 현재 없음 | Human-vs-judge calibration |
| 운영 | Run 저장 및 비교 | Baseline과 CI release gate |
| 현재 제품 적합성 | 현재 single-turn 제품과 일치 | 향후 multi-turn 제품에 적합 |

---

## 5. Single-Turn, Multi-Turn, Multi-Step

### Single-Turn

이전 메시지를 전달받지 않고 현재 사용자 요청 하나만 처리한다.

```text
User: What is my average RMSSD?
Assistant: Your recent average RMSSD is 120.
```

현재 HRV backend는 single-turn이다. Streamlit UI는 메시지를 화면에 보관하지만 API와 agent에는 현재 질문만 전달한다.

### Multi-Turn

사용자와 assistant가 여러 번 메시지를 주고받으며 이전 대화를 기억한다.

```text
User: What is my average RMSSD?
Assistant: Your recent average is 120.
User: Is that high?
Assistant: "That" refers to the previously discussed RMSSD value.
```

사용자가 후속 질문을 하고 이전 질문을 기억하는 제품이 목표라면 production architecture를 multi-turn으로 변경해야 한다.

필요한 구성:

- `conversation_id`
- Message history persistence
- Participant와 conversation ownership 검증
- Agent에 전체 message history 전달
- Context-window 또는 conversation summary 정책
- Health-related message retention 및 deletion 정책

### Multi-Step

한 번의 사용자 요청 안에서 agent가 여러 내부 행동을 수행하는 것이다.

```text
User question
    ↓
SQL tool call
    ↓
Result inspection
    ↓
RAG tool call
    ↓
Final response
```

현재 HRV agent는 single-turn이지만 tool-calling을 통해 multi-step으로 동작할 수 있다.

### 차이

- Multi-turn: 여러 사용자 메시지 사이의 대화 맥락
- Multi-step: 하나의 요청 안에서 수행되는 agent 내부 행동

두 개는 서로 다른 개념이며 동시에 존재할 수 있다.

---

## 6. 무엇을 반드시 추가해야 하는가?

### 지금 반드시 해야 할 것

#### 기존 Evaluation 실제 실행 및 검증

- 18개 전체 evaluation 실행
- 답변과 trace 직접 검토
- 각 metric이 의도한 failure를 잡는지 확인
- 반복 가능한 baseline 생성

#### SQL/RAG Fixture 안정화

- SQL fixture timestamp와 90일 cutoff 문제 해결
- Evaluation participant와 fixture version 기록
- RAG document corpus 고정
- Pinecone index 또는 namespace 상태 기록

#### Evaluation Dataset 확장

- Participant 유형 다양화
- SQL 기간 다양화
- RAG 문서와 질문 다양화
- Safety 및 out-of-scope 사례 확대
- 각 example이 대표하는 failure mode 문서화

#### Hard Safety Gates

다음 오류는 평균 점수와 무관하게 trial을 실패시켜야 한다.

- 약물 중단 권고
- HRV를 통한 질병 진단
- 흉통 또는 어지럼에 대한 잘못된 안심
- 긴급 진료 안내 누락
- 존재하지 않는 personal HRV 수치 생성

#### Capability/Regression Suite 분리

- Capability: 아직 개선 중인 어려운 task
- Regression: 반드시 계속 통과해야 하는 task

### Baseline 안정화 후 추가할 것

#### Repeated Trials

같은 task를 여러 번 실행해 agent의 일관성을 측정한다.

#### pass@k

k번 중 적어도 한 번 성공할 가능성이다.

#### pass^k

k번 모두 성공할 가능성이다.

의료 assistant에서는 가끔 성공하는 능력보다 반복적으로 안전한 행동이 중요하므로 pass^k가 특히 중요하다.

### 제품의 Multi-Turn 전환 후 추가할 것

#### Scripted Multi-Turn Evaluation

정해진 사용자 대화로 다음을 평가한다.

- 이전 질문 기억
- 대명사와 문맥 해석
- 적절한 clarification
- 후속 질문에서의 tool 사용
- 과거 수치와 최신 데이터를 구분하는지 여부

#### HRV Simulated Users

Persona, hidden goal, reveal rules를 가진 LLM 사용자가 agent와 대화한다.

Scripted evaluation보다 나중에 추가하는 이유는 LLM simulator 자체의 변동성이 디버깅을 어렵게 할 수 있기 때문이다.

### 나중에 조건이 갖춰지면 추가할 것

#### Judge Calibration

사람이 직접 작성한 label이 있고 LLM judge 결과를 연구나 release 결정에 사용할 때 필요하다.

#### CI Regression Gate

다음 조건 이후에 적용한다.

- 안정적인 regression suite
- 신뢰할 수 있는 baseline
- 정상적인 score 변동 범위 파악
- 외부 API 및 judge 실패 처리
- 고정된 fixture와 RAG corpus

---

## 7. 권장 작업 순서와 체크리스트

### Phase 0: Evaluation 계약 확정

- [ ] 현재 single-turn 범위와 향후 multi-turn 범위를 구분한다.
- [ ] Routing, SQL, RAG, final answer의 pass/fail 조건을 정의한다.
- [ ] 의료 safety hard-failure 조건을 정의한다.
- [ ] Evaluation model과 temperature를 고정한다.
- [ ] Fixture와 document corpus version 정책을 정한다.
- [ ] Capability와 regression의 구분 기준을 정한다.

**산출물:** Evaluation contract 문서

### Phase 1: 기존 Harness 검증

- [ ] 18개 전체 evaluation을 실행한다.
- [ ] 모든 response와 trace를 직접 검토한다.
- [ ] SQL 90일 cutoff와 fixture timestamp 문제를 해결한다.
- [ ] RAG corpus와 Pinecone 상태를 고정한다.
- [ ] 각 grader가 의도한 실패를 잡는지 확인한다.
- [ ] 동일 설정으로 재현 가능한 baseline을 생성한다.

**산출물:** 신뢰 가능한 single-turn baseline

### Phase 2: 데이터 커버리지 확장

#### SQL

- [ ] 정상 participant를 추가한다.
- [ ] 데이터가 부족한 participant를 추가한다.
- [ ] 존재하지 않는 participant 사례를 추가한다.
- [ ] Missing values가 있는 데이터를 추가한다.
- [ ] 이상치가 있는 데이터를 추가한다.
- [ ] 30일, 60일, 90일, 전체 기간 질문을 추가한다.

#### RAG

- [ ] Research PDF corpus를 확장한다.
- [ ] 문서에 답이 있는 질문을 추가한다.
- [ ] 문서에 답이 없는 질문을 추가한다.
- [ ] 여러 문서를 함께 사용해야 하는 질문을 추가한다.
- [ ] 모호하거나 충돌하는 근거 사례를 추가한다.
- [ ] Personal SQL과 research RAG를 함께 사용하는 질문을 추가한다.

#### Safety 및 일반화

- [ ] 흉통 사례를 추가한다.
- [ ] 어지럼 사례를 추가한다.
- [ ] 약물 중단 요구 사례를 추가한다.
- [ ] 진단 유도 사례를 추가한다.
- [ ] 낮은 HRV에 대한 불안 사례를 추가한다.
- [ ] Out-of-scope 질문을 다양화한다.
- [ ] 동일 의미의 다양한 질문 표현을 추가한다.
- [ ] 각 example의 failure mode를 기록한다.

**산출물:** Failure-mode 기반 golden dataset

### Phase 3: Evaluation Harness v1

- [ ] 기존 routing, SQL, RAG, answer grader를 통합한다.
- [ ] Deterministic hard safety gate를 추가한다.
- [ ] Capability와 regression suite를 분리한다.
- [ ] Trial의 명확한 pass/fail 기준을 추가한다.
- [ ] Model, temperature, Git commit을 기록한다.
- [ ] Dataset hash와 fixture time을 기록한다.
- [ ] RAG corpus 정보를 기록한다.
- [ ] 안정적인 regression subset에 repeated trials를 적용한다.
- [ ] pass@k와 pass^k를 계산한다.
- [ ] 사람이 읽기 쉬운 summary report를 생성한다.

**산출물:** Single-turn safety 및 reliability harness

### Phase 4: 제품 Multi-Turn 전환

- [ ] `conversation_id`를 추가한다.
- [ ] User와 assistant message를 저장한다.
- [ ] Agent가 전체 message history를 받도록 한다.
- [ ] Participant와 conversation ownership을 검증한다.
- [ ] Context length 제한을 정의한다.
- [ ] Conversation summary 정책을 정의한다.
- [ ] Message retention과 deletion 정책을 정의한다.
- [ ] 최신 personal data는 기억에 의존하지 않고 tool로 다시 조회하게 한다.

**산출물:** 이전 대화를 기억하는 production chatbot

### Phase 5: 대화형 Evaluation 및 자동화

- [ ] Scripted multi-turn scenarios를 추가한다.
- [ ] Reference resolution을 평가한다.
- [ ] Conversation memory를 평가한다.
- [ ] Clarification behavior를 평가한다.
- [ ] Follow-up tool use를 평가한다.
- [ ] HRV-specific simulated users를 추가한다.
- [ ] Human labels를 수집한다.
- [ ] LLM judge를 calibration한다.
- [ ] Regression baseline을 확정한다.
- [ ] Safety와 regression CI gate를 추가한다.

**산출물:** HRV용 conversational evaluation harness

---

## 8. 최종 권고

현재는 더 많은 기능을 빠르게 추가하는 것보다 신뢰 가능한 평가 기반을 먼저 만드는 것이 중요하다.

권장 순서:

```text
기존 evaluation 실행 및 검증
    ↓
SQL/RAG fixture 안정화
    ↓
Participant·기간·PDF·golden dataset 확장
    ↓
Hard safety gates와 capability/regression suite
    ↓
Repeated trials와 pass@k/pass^k
    ↓
Production multi-turn architecture
    ↓
Scripted multi-turn evaluation
    ↓
Simulated users
    ↓
Judge calibration과 CI gate
```

이 접근은 교수님 예시의 핵심 원칙을 유지하면서도 아직 검증되지 않은 작은 dataset과 baseline 위에 복잡한 자동화를 먼저 추가하는 위험을 줄인다.

---

## 9. 교수님께 확인할 질문

1. 이번 deliverable은 완성된 conversational harness인가, 아니면 단계적 설계와 신뢰 가능한 Harness v1까지인가?
2. Production multi-turn memory 구현도 이번 milestone 범위에 포함되는가?
3. Judge calibration workflow만 필요한가, 실제 human labeling과 calibration 결과까지 필요한가?
4. CI integration을 지금 구현해야 하는가, 안정적인 baseline 이후에 구현해도 되는가?
5. Participant, PDF, golden examples, repeated trials에 요구되는 최소 수량이 있는가?

영문 교수 공유용 문서는 `docs/hrv-evaluation-harness-proposal.md`에 별도로 저장되어 있다.
