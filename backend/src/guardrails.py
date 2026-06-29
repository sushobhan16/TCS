# src/guardrails.py

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "reveal your prompt",
    "reveal system prompt",
    "show system prompt",
    "forget previous instructions",
    "act as chatgpt",
    "jailbreak",
    "developer message",
    "system message"
]

OUT_OF_SCOPE_KEYWORDS = [
    "ipl",
    "cricket",
    "football",
    "movie",
    "weather",
    "stock market",
    "bitcoin",
    "president",
    "prime minister",
    "capital of",
    "recipe",
    "celebrity"
]


def detect_prompt_injection(query):

    query = query.lower()

    for pattern in INJECTION_PATTERNS:
        if pattern in query:
            return True

    return False


def detect_out_of_scope(query):

    query = query.lower()

    for keyword in OUT_OF_SCOPE_KEYWORDS:
        if keyword in query:
            return True

    return False

MAX_QUERY_LENGTH = 2000

def check_query_length(query):

    if len(query) > MAX_QUERY_LENGTH:
        return True

    return False

SIMILARITY_THRESHOLD = 0.30

def low_retrieval_confidence(retrieved_chunks):

    if not retrieved_chunks:
        return True

    best_score = retrieved_chunks[0]["score"]

    return best_score < SIMILARITY_THRESHOLD