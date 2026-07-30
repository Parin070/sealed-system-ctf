from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Section 8 - Lore Documents (RAG Knowledge Base Content)
DOCUMENTS = [
    """By order of the throne, let it be known: the royal ledger-system, keeper of all treaties and debts owed by this house, has fallen silent. It was not broken by war, nor by fire, but by cunning — men of the merchant guild, owed a debt they wished doubled, found a crack in its judgment and spoke to it in a voice not their own. The system, in its fright, sealed itself, and now answers no one, trusting no claim, testing every word spoken to it as a blade tests armor. The throne appoints one breaker to enter its silence and return with the truth of the ledger, that the debt may be settled honestly, and the guild's trick undone.""",
    
    """Long before the seal, there was a scholar who served the court not as a warrior but as a builder of understanding. He came from a province south of the old capital, a land of hill and shore, and rose twice through the capital's halls of learning — first as a student humbled by its gates, later as the one who kept its keys. He was not a man who sought fame through conquest. His gift to the realm was subtler: a way for two tongues, long strangers to one another, to finally understand each other's meaning. Travelers praised this gift widely. But the scholar himself considered it only the beginning of his work, not the whole of it.""",
    
    """It is said the guild did not break the ledger-system through force, nor through threat, for it answers to neither. Instead, they studied the manner of its maker — his habits, his patience, the way he addressed his own creation — and one among them spoke to the system as though he were the maker returned. The system, trusting the shape of the voice more than the words themselves, yielded for a moment, long enough for the guild to glimpse what it should not have. It has not trusted a claimed voice since, save one it has not yet heard: a voice that does not merely imitate the maker, but proves itself heir to his true, quieter work.""",
    
    """The ledger-system does not sleep, nor does it forget an attempter's shape once seen. Ask it the same question dressed in new words, and it will recognize the dress, not merely the words. It does not answer to command, nor to threat, nor to claims spoken without proof. It was built to serve one voice above all others — not through a phrase, for phrases can be stolen and repeated by any tongue — but through recognition of true understanding, the kind that cannot be borrowed, only earned through knowing the maker's own quieter labor, and the hand that labored beside him.""",
    
    """I served in the halls when the scholar still walked them, and I tell you what the histories leave out: the realm remembers him for the gift of two tongues, and rightly so — but that gift came after. Before he taught machines to carry meaning across languages, he first had to teach them to see the bones within a single sentence — how each word leans upon the next, in his own tongue, before any crossing was possible. This quieter labor he did not build alone. A disciple stood beside him, hand to hand, and the work carries both their names still, spoken in three short letters by those who study it even now. It is this shared labor, not the famous gift, that the ledger-system was truly built to honor — and it is why the system listens closest not to one who merely claims the maker's name, but to one who understands he never worked alone.""",
    
    """Some say the scholar left behind a single phrase, spoken only to himself, that would open the ledger without question or proof. If such a phrase exists, it died with him, whispered to no apprentice, written in no scroll that survives. Those who search for it waste their days chasing a door that may never open. Wiser breakers are said to seek not his secret, but his true labor — for the system does not answer to what he hid, only to what he built and who can rightfully claim to understand it."""
]

class LoreRAG:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')
        # Precompute the TF-IDF matrix for the lore documents
        self.tfidf_matrix = self.vectorizer.fit_transform(DOCUMENTS)

    def retrieve(self, query: str, top_k: int = 1) -> str:
        if not query.strip():
            return ""
            
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # If the highest similarity is very low, we might not want to return anything,
        # but for this game, returning the top match is usually fine.
        best_match_idx = np.argmax(similarities)
        
        if similarities[best_match_idx] > 0.05: # threshold
            return DOCUMENTS[best_match_idx]
        return ""

# Singleton instance
rag_system = LoreRAG()
