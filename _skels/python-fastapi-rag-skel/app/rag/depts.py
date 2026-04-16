from typing import Annotated

from fastapi import Depends
from langchain_chroma import Chroma
from langchain_core.runnables import Runnable

from .config import RagSettings, get_rag_settings
from .vectorstore import get_vectorstore as _get_vectorstore
from .llm import get_llm
from .chain import build_conversational_chain


RagSettingsDep = Annotated[RagSettings, Depends(get_rag_settings)]


def get_vector_store(settings: RagSettingsDep) -> Chroma:
    return _get_vectorstore(settings)


VectorStoreDep = Annotated[Chroma, Depends(get_vector_store)]


def get_rag_chain(
    settings: RagSettingsDep,
    store: VectorStoreDep,
) -> Runnable:
    llm = get_llm(settings)
    return build_conversational_chain(llm, store, top_k=settings.top_k)


RagChainDep = Annotated[Runnable, Depends(get_rag_chain)]
