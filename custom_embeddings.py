from typing import List
from langchain_community.embeddings import OpenAIEmbeddings

class CustomOpenAIEmbeddings(OpenAIEmbeddings):
    """
    Custom OpenAIEmbeddings to bypass tokenization check which sends tokens instead of strings,
    causing compatibility issues with LM Studio (which expects strings).
    """
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Bypass the length check and tokenization, send texts directly
        # Note: This assumes texts are not too long for the model
        response = self.client.create(
            input=texts,
            model=self.model
        )
        # Extract embeddings from response
        # Handle both object (openai>=1.0) and dict (older) response formats
        if hasattr(response, 'data'):
            return [data.embedding for data in response.data]
        else:
            return [data['embedding'] for data in response['data']]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
