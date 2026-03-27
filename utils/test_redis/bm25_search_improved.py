from redis import Redis
from redis.commands.search.query import Query
import nltk
from nltk.tokenize import word_tokenize
import string

import re

from itertools import combinations

# Define a color code for highlighting
HIGHLIGHT_START = "\033[1;31m"  # Bold red
HIGHLIGHT_END = "\033[0m"       # Reset color
WINDOW_SIZE = 30  # Number of characters around the keyword to display

client = Redis.from_url("redis://localhost:6379")

def search(query: str):
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab')
    # Break down the query into tokens
    tokens = word_tokenize(query)
    non_puncts = list(filter(lambda token: token not in string.punctuation, tokens))
    pattern = f"[{re.escape(string.punctuation)}]"
    orig_keywords = [re.sub(pattern, lambda match: f"\\{match.group(0)}", keyword) for keyword in non_puncts]

    # orig_keywords = [f"%{keyword}%" for keyword in orig_keywords]

    keywords = []
    weights = []
    TUPLE_LIMIT = 4
    BOOST_FACTOR = 2
    for i in range(1, TUPLE_LIMIT + 1):
        for combo in combinations(orig_keywords, i):
            keywords.append(" ".join(combo))
            weights.append(BOOST_FACTOR ** (i - 1))

    # params = {f"keyword_{i}": keyword for i, keyword in enumerate(keywords)}
    # # # `|` means searching the union of the words/tokens
    # # # `%` means fuzzy search with Levenshtein distance of 1
    # query_str = " | ".join([f"(${param}) => {{ $weight: {weight} }}" for param, weight in zip(params, weights)])
    # query_str = "@text:(" + query_str + ")"

    # fuzzy = [" ".join([f"%{t}%" for t in keyword.split(" ")]) for keyword in keywords]
    query_str = " | ".join([f"({keyword}) => {{ $weight: {weight} }}" for keyword, weight in zip(keywords, weights)])
    query_str = "@text:(" + query_str + ")"
    
    # query_str = " | ".join([f"@text:({keyword}) => {{ $weight: {weight} }}" for keyword, weight in zip(keywords, weights)])

    # query_str = "@text:((Yaolin) => { $weight: 1 } | (Liu) => { $weight: 1 } | (Yaolin Liu) => { $weight: 100 })"
    
    print(query_str)
    print(keywords)
    # print(params)

    retriever_top_k = 10
    query_cmd = Query(query_str).scorer("BM25").paging(0, retriever_top_k).with_scores()
    result = client.ft("idx:test").search(query_cmd)

    # query_cmd = Query(query_str).dialect(2).scorer("BM25").paging(0, retriever_top_k).with_scores()
    # result = client.ft("idx:test").search(query_cmd, params)

    # result = client.ft("idx:test_1").search(query_cmd, params)
    
    print("###")

    # for d in result.docs:
    #     print(f"Score: {d.score}")
    #     print("Text: " + d.text.replace("\n", " ")[:500])
    #     print("---")

    for d in result.docs:
        highlighted_text = d.text
        snippets = []
        
        # For each keyword, find matches in the text and extract surrounding context
        for keyword in keywords:
            matches = [(m.start(), m.end()) for m in re.finditer(re.escape(keyword), highlighted_text, flags=re.IGNORECASE)]
            for start, end in matches:
                # Calculate start and end of the context window around each match
                context_start = max(0, start - WINDOW_SIZE)
                context_end = min(len(highlighted_text), end + WINDOW_SIZE)
                # Highlight the keyword within the context
                context_snippet = (
                    highlighted_text[context_start:start]
                    + HIGHLIGHT_START + highlighted_text[start:end] + HIGHLIGHT_END
                    + highlighted_text[end:context_end]
                )
                snippets.append(context_snippet.replace("\n", " "))
    
        # Join all context snippets with ellipses for readability
        final_snippets = "\n".join(snippets)
        
        print(f"Score: {d.score}")
        print("Text:\n" + final_snippets)
        print("---")

    print("###")
    print()

# print(word_tokenize("yo, what's up? man! bruh... done. 666 667."))

# search("alpha beta")
# search("can't, do")
# search("yaolin liu")
search("who is professor bing luo")
