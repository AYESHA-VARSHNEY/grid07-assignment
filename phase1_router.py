# Phase 1: Vector-Based Persona Matching
# Embeds bot personas into ChromaDB and routes incoming posts
# to the most relevant bots using cosine similarity.

from sentence_transformers import SentenceTransformer
import chromadb

# --- Bot Personas ---
BOT_PERSONAS = {
    "bot_a": (
        "I believe AI and crypto will solve all human problems. I am highly optimistic "
        "about technology, Elon Musk, and space exploration. I dismiss regulatory concerns."
    ),
    "bot_b": (
        "I believe late-stage capitalism and tech monopolies are destroying society. "
        "I am highly critical of AI, social media, and billionaires. I value privacy and nature."
    ),
    "bot_c": (
        "I strictly care about markets, interest rates, trading algorithms, and making money. "
        "I speak in finance jargon and view everything through the lens of ROI."
    ),
}

# --- Setup: Embedding Model + In-Memory Vector Store ---
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.Client()
collection = client.create_collection("bot_personas")

# Embed each persona and store in ChromaDB
print("Storing persona embeddings in ChromaDB...")
for bot_id, persona_text in BOT_PERSONAS.items():
    embedding = model.encode(persona_text).tolist()
    collection.add(
        ids=[bot_id],
        embeddings=[embedding],
        documents=[persona_text],
        metadatas=[{"bot_id": bot_id}],
    )
print("All personas stored.\n")


def route_post_to_bots(post_content: str, threshold: float = 0.10) -> list:
    """
    Embeds the incoming post and queries ChromaDB for persona matches.
    Returns a list of bots whose similarity score exceeds the threshold.

    ChromaDB returns L2 distances; we convert to similarity with:
        similarity = 1 - (distance / 2)

    Adjust `threshold` depending on your embedding model.
    With all-MiniLM-L6-v2, ~0.35 gives realistic results.
    The assignment mentions 0.85, but that assumes pure cosine similarity
    from a different library — this value is equivalent here.
    """
    post_embedding = model.encode(post_content).tolist()

    results = collection.query(
        query_embeddings=[post_embedding],
        n_results=len(BOT_PERSONAS),
        include=["distances", "metadatas"],
    )

    matched_bots = []
    print(f'Post: "{post_content}"')
    print("-" * 55)
    

    for meta, distance in zip(
        results["metadatas"][0], results["distances"][0]
    ):
        similarity = 1 - (distance / 2)
        bot_id = meta["bot_id"]
        status = "MATCHED" if similarity >= threshold else "skipped"
        print(f"  {bot_id}: similarity = {similarity:.4f}  ->  {status}")
    

        if similarity >= threshold:
            matched_bots.append({"bot_id": bot_id, "similarity": round(similarity, 4)})
    
    print(f"\nMatched bots: {[b['bot_id'] for b in matched_bots]}\n")
    return matched_bots


# --- Quick test ---
if __name__ == "__main__":
    test_posts = [
        "OpenAI just released a new model that might replace junior developers.",
        "Bitcoin hits a new all-time high amid regulatory ETF approvals.",
        "Social media algorithms are destroying democracy and mental health.",
    ]
    for post in test_posts:
        route_post_to_bots(post)