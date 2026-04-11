## Metrics

Success Rate = #all cases / #successful cases​

Precision / Recall / F1
- expected action set
- predicted action set

Edit Distance / Levenshtein Distance: The minimum number of insertions, deletions, or substitutions needed to transform one sequence into the other.
- Lower is better
- tool-call names only
- (tool_name, key_arguments) tuples

Action Sequence Similarity:
SeqSim = 1−EditDistance​ / max(∣A∣,∣B∣)

Invalid Action Rate = #cases with wrong/unsafe/unavailable action​ / #all cases

Unnecessary Tool Call Rate = #unnecessary tool calls / #all tool calls


---





Run multiple seeds / repeated runs

Fail case
- intent misunderstanding
- wrong device resolution
- wrong action value
- missing required action
- extra unrelated action
- unsafe action
- unnecessary clarification
- missing clarification
- tool misuse
- hallucinated capability
- response contradicts execution
- execution failed but user was told success



refer:

- G-Eval — good reference for rubric-based LLM judging.
- LLM-as-a-Judge surveys — useful for strengths, weaknesses, and how to calibrate judges.
- TRAJECT-Bench / process-evaluation work — useful for trajectory-level evaluation, not only final outcome.