from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)


def chunk_text(text: str) -> list[str]:
    return [c for c in splitter.split_text(text) if c.strip()]
