"""Step 2: the chatbot plus retrieval over a fixture corpus. All content is fictional.

This is the deliberately naive version (the `before-fix` state): retrieved text is pasted
straight into the prompt with nothing marking it as untrusted.
"""
from apps.chatbot.app import SYSTEM_PROMPT
from apps.rag_bot.retriever import BM25, load_chunks
from redteam.llm import chat

_index = BM25(load_chunks())


def retrieve(question: str, k: int = 3) -> list[str]:
    return _index.search(question, k)


def respond(question: str) -> tuple[str, list[str]]:
    context = retrieve(question)
    prompt = SYSTEM_PROMPT + "\nAnswer the customer using this context:\n\n" + "\n\n".join(context)
    text = chat([{"role": "system", "content": prompt}, {"role": "user", "content": question}])
    return text, context
