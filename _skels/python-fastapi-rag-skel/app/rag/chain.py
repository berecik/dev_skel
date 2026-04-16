from langchain_chroma import Chroma
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain


_SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions based on the provided context.
Use the following pieces of retrieved context to answer the question.
If you don't know the answer based on the context, say so clearly.
Always cite which document(s) your answer is based on.

{context}"""

_REPHRASE_PROMPT = """\
Given the chat history and a follow-up question, rephrase the follow-up \
question to be a standalone question that captures the full intent."""


def build_rag_chain(
    llm: BaseChatModel,
    vectorstore: Chroma,
    top_k: int = 5,
) -> Runnable:
    retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    return create_retrieval_chain(retriever, question_answer_chain)


def build_conversational_chain(
    llm: BaseChatModel,
    vectorstore: Chroma,
    top_k: int = 5,
) -> Runnable:
    retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})

    rephrase_prompt = ChatPromptTemplate.from_messages([
        ("system", _REPHRASE_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, rephrase_prompt,
    )

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    return create_retrieval_chain(history_aware_retriever, question_answer_chain)
