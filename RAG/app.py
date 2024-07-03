import streamlit as st
from query import get_pipeline
from settings import Config, setup, get_parser

# Parse the existing arguments (you can prefill them with default values, as the user won't provide them in the web interface)
parser = get_parser()
args = parser.parse_args(args=[])  # Empty list since no CLI arguments are provided
setup(args)

# Define the main Streamlit interface function
def main():
    st.title("DKU LLM v1.0")
    st.info("powered by LlamaIndex 💬🦙")

    # Text box for user input
    query = st.text_input("Enter your query about DKU:")

    # Button to run the query
    if st.button("Get Response"):
        if query:  # If the query is not empty
            with st.spinner("Fetching response..."):
                # Obtain the pipeline defined in query.py
                pipeline = get_pipeline(
                    retriever_type="fusion",
                    hyde=True,
                    vector_top_k=5,
                    bm25_top_k=5,
                    fusion_top_k=5,
                    fusion_mode="reciprocal_rank",
                    num_queries=3,
                    synthesize_response=True,
                    response_mode="compact",
                )
                # Run the pipeline with the user's query
                output = pipeline.run(input=query)
                
                st.text("Response:")
                st.write(output)  # Display the response
        else:
            st.warning("Please enter a valid query.")

# Run the Streamlit app
if __name__ == "__main__":
    main()
