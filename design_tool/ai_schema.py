AI_RESPONSE_SCHEMA_VERSION = "1.0"


MODE_ENUM = [
    "question_group",
    "confirmation",
    "readiness_check",
    "full_project_output",
    "partial_project_output",
    "maintenance",
    "error",
]

TURN_MODE_ENUM = [
    "question_group",
    "confirmation",
    "readiness_check",
    "maintenance",
    "error",
]


ROUTE_OVERVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "currentMdaStage",
        "expectedDomains",
        "completedNodes",
        "clarificationTargets",
        "lowApplicabilityCandidates",
    ],
    "properties": {
        "currentMdaStage": {"type": "string"},
        "expectedDomains": {"type": "array", "items": {"type": "string"}},
        "completedNodes": {"type": "array", "items": {"type": "string"}},
        "clarificationTargets": {"type": "array", "items": {"type": "string"}},
        "lowApplicabilityCandidates": {"type": "array", "items": {"type": "string"}},
    },
}

QUESTION_GROUP_SCHEMA = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "required": ["id", "mdaStage", "purpose", "questions"],
    "properties": {
        "id": {"type": "string"},
        "mdaStage": {"type": "string"},
        "purpose": {"type": "string"},
        "questions": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "reason", "targetNodeIds"],
                "properties": {
                    "text": {"type": "string"},
                    "reason": {"type": "string"},
                    "targetNodeIds": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

READINESS_CHECK_SCHEMA = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "required": ["ready", "confidence", "message", "askUser"],
    "properties": {
        "ready": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "message": {"type": "string"},
        "askUser": {"type": "string"},
    },
}

INFERENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "nodeId",
        "itemId",
        "groupId",
        "optionIds",
        "confidence",
        "reason",
        "applicabilityScore",
        "applicabilityReason",
        "notApplicable",
    ],
    "properties": {
        "nodeId": {"type": "string"},
        "itemId": {"type": "string"},
        "groupId": {"type": "string"},
        "optionIds": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
        "applicabilityScore": {"type": "number", "minimum": 0, "maximum": 1},
        "applicabilityReason": {"type": "string"},
        "notApplicable": {"type": "boolean"},
    },
}

FULL_PROJECT_OUTPUT_SCHEMA = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "required": ["projectStateJson", "confidenceMapJson", "summary"],
    "properties": {
        "projectStateJson": {"type": "string"},
        "confidenceMapJson": {"type": "string"},
        "summary": {"type": "string"},
    },
}

PARTIAL_PROJECT_OUTPUT_SCHEMA = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "required": ["domainIds", "projectStatePatchJson", "confidenceMapJson", "summary"],
    "properties": {
        "domainIds": {"type": "array", "items": {"type": "string"}},
        "projectStatePatchJson": {"type": "string"},
        "confidenceMapJson": {"type": "string"},
        "summary": {"type": "string"},
    },
}

OPTION_DIFFERENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "nodeId", "itemId", "groupId", "before", "after", "confidence"],
    "properties": {
        "type": {"type": "string"},
        "nodeId": {"type": "string"},
        "itemId": {"type": "string"},
        "groupId": {"type": "string"},
        "before": {"type": "array", "items": {"type": "string"}},
        "after": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def base_response_properties(mode_enum):
    return {
        "schemaVersion": {"type": "string"},
        "mode": {"type": "string", "enum": mode_enum},
        "assistantMessage": {"type": "string"},
        "routeOverview": ROUTE_OVERVIEW_SCHEMA,
    }


AI_TURN_RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Commercial game design AI interview turn response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "mode",
        "assistantMessage",
        "routeOverview",
        "questionGroup",
        "readinessCheck",
        "inferences",
    ],
    "properties": {
        **base_response_properties(TURN_MODE_ENUM),
        "questionGroup": QUESTION_GROUP_SCHEMA,
        "readinessCheck": READINESS_CHECK_SCHEMA,
        "inferences": {"type": "array", "items": INFERENCE_SCHEMA},
    },
}

AI_READINESS_RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Commercial game design AI interview readiness response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "mode",
        "assistantMessage",
        "routeOverview",
        "readinessCheck",
        "inferences",
    ],
    "properties": {
        **base_response_properties(["readiness_check", "maintenance", "error"]),
        "readinessCheck": READINESS_CHECK_SCHEMA,
        "inferences": {"type": "array", "items": INFERENCE_SCHEMA},
    },
}

AI_FULL_OUTPUT_RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Commercial game design AI interview full output response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "mode",
        "assistantMessage",
        "routeOverview",
        "fullProjectOutput",
        "optionDifferences",
        "inferences",
    ],
    "properties": {
        **base_response_properties(MODE_ENUM),
        "questionGroup": QUESTION_GROUP_SCHEMA,
        "readinessCheck": READINESS_CHECK_SCHEMA,
        "inferences": {"type": "array", "items": INFERENCE_SCHEMA},
        "fullProjectOutput": FULL_PROJECT_OUTPUT_SCHEMA,
        "optionDifferences": {"type": "array", "items": OPTION_DIFFERENCE_SCHEMA},
    },
}

AI_PARTIAL_OUTPUT_RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Commercial game design AI interview partial output response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "mode",
        "assistantMessage",
        "routeOverview",
        "partialProjectOutput",
        "inferences",
    ],
    "properties": {
        **base_response_properties(["partial_project_output", "maintenance", "error"]),
        "inferences": {"type": "array", "items": INFERENCE_SCHEMA},
        "partialProjectOutput": PARTIAL_PROJECT_OUTPUT_SCHEMA,
    },
}

AI_MAPPING_RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Commercial game design AI interview background mapping response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "mode",
        "assistantMessage",
        "inferences",
    ],
    "properties": {
        "schemaVersion": {"type": "string"},
        "mode": {"type": "string", "enum": ["mapping", "maintenance", "error"]},
        "assistantMessage": {"type": "string"},
        "inferences": {"type": "array", "items": INFERENCE_SCHEMA},
    },
}

AI_SUMMARY_RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Commercial game design AI interview summary correction response",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "mode",
        "summary",
    ],
    "properties": {
        "schemaVersion": {"type": "string"},
        "mode": {"type": "string", "enum": ["summary_correction", "maintenance", "error"]},
        "summary": {"type": "object"},
    },
}

AI_RESPONSE_SCHEMAS = {
    "turn": AI_TURN_RESPONSE_SCHEMA,
    "readiness": AI_READINESS_RESPONSE_SCHEMA,
    "full_output": AI_FULL_OUTPUT_RESPONSE_SCHEMA,
    "partial_output": AI_PARTIAL_OUTPUT_RESPONSE_SCHEMA,
    "mapping": AI_MAPPING_RESPONSE_SCHEMA,
    "summary": AI_SUMMARY_RESPONSE_SCHEMA,
}

# Backward-compatible alias for callers that still expect one canonical schema.
AI_RESPONSE_SCHEMA = AI_FULL_OUTPUT_RESPONSE_SCHEMA
