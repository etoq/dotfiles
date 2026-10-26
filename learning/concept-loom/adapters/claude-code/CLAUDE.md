# Concept Loom

For requests to learn, study, practise, understand, or receive an explanation, load the `concept-coach` skill. Use the `concept-loom` MCP tools to prepare and assess knowledge checks, maintain learning notebooks, and show Mermaid or text diagrams directly in the conversation.

Use `AskUserQuestion` to present returned checkpoint choices and to collect preferences. Do not reveal expected keys or the private rationale before the learner answers.


## ConceptLoom protocol: 2

Use `loom_status` and the explicit project session when resuming; begin a distinct lesson without restarting diagnosis. Bind checkpoints to the session and concept. Record exact responses, actual output and explicit assistance; omitted help is unknown. Open grading needs criterion IDs and quotations from the response. Record actual route consent with `loom_approve_route`. Unchanged state fields are preserved, and configured event-based notebook/current-stage records update automatically. Inspect commit and projection issues; retry a committed operation using its stable ID or synchronize its projections, without duplicating the learner attempt.
