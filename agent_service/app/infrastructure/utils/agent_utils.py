
from agno.agent import Agent
from app.infrastructure.agents_backend.model_provider import model
import re
from agno.knowledge.chunking.document import DocumentChunking
from agno.knowledge.document.base import Document
from app.infrastructure.utils.json_text_chunker import SmartJsonChunker



# ===========================================================
# Utility to safely send long prompts to an Agno Agent
# ===========================================================
def runOptimizedPrompt(agent: Agent, prompt: str, max_tokens: int = 50000, use_summarizer: bool = False): 
    """
    Handles large prompts automatically:
    - If prompt is small enough, sends directly.
    - If too large, splits into chunks and summarizes each.
    - Combines summaries into a final summarized response.
    """
    
    promptLength = len(prompt)
    
    # 1. Create a temporary summarizer (smaller model for efficiency)
    summarizer = Agent(
        name="summarizer",
        use_json_mode=True,
        model=model,
        instructions="Summarize text/json concisely, keeping only key logic, flow, and purpose.",
    )
    
    # 2. If prompt fits in limit — send directly
    if promptLength <= max_tokens:
        if use_summarizer:
          return summarizer.run(f"Summarize this section of code or text:\n{prompt}")
        else:    
          return agent.run(prompt)

    print(f"[INFO] Large prompt detected ({promptLength} chars) — chunking & summarizing...")

    

    # 3. Chunk the prompt
    # chunks = content_aware_chunk(prompt, promptLength, max_tokens)
    
    
    chunker = SmartJsonChunker(target_tokens=max_tokens)
    chunks = chunker.chunk(prompt)
    print(f"[INFO] Total chunks {len(chunks)}...")


    # 4. Summarize each chunk
    summaries = []
    for i, chunk in enumerate(chunks):
        print(f"[INFO] Summarizing chunk {i+1}/{len(chunks)}...")
        summary = summarizer.run(f"Summarize this section of code or text:\n{chunk}")
        summaries.append(summary.content)

    # 5. Merge the summaries into one
    combined_summary = "\n\n".join(summaries)
    print("[INFO] Combining summarized chunks...")

    # 6. Send the merged summary to the main agent
    final_response = agent.run(
        f"This is a summarized version of a large input:\n\n{combined_summary}\n\nNow answer based on this."
    )

    return final_response


# def content_aware_chunk(text: str, promptLength: int, max_tokens: int):
#     """
#     Perform content-aware chunking of the text using different separators for different content types.
    
#     Parameters:
#     text (str): The input text to be chunked.
    
#     Returns:
#     list: A list of text chunks.
#     """
#     # Define separators for different content types
#     # paragraph_separator = r'\n\n+'
#     # bullet_point_separator = r'\n- '
#     # numbered_list_separator = r'\n\d+\. '
    
#     # maxSplit = int((promptLength / max_tokens) - 1)
    
#     documnetChunk = DocumentChunking(chunk_size=10000, overlap=200)
#     docs = documnetChunk.chunk(document=Document(content=text))

#     # First, split the text by paragraphs
#     # paragraphs = re.split(paragraph_separator, text, maxsplit=(max_tokens-100))

#     # Initialize list to hold all chunks
#     chunks = []

#     for doc in docs:
#         # Check for bullet points
#         # if re.search(bullet_point_separator, paragraph):
#         #     chunks.extend(re.split(bullet_point_separator, paragraph))
#         # # Check for numbered lists
#         # elif re.search(numbered_list_separator, paragraph):
#         #     chunks.extend(re.split(numbered_list_separator, paragraph))
#         # else:
#         # Treat as a regular paragraph
#         print(f"Chunk Size: {len(doc.content)}...")
#         chunks.append(doc.content)

#     return chunks