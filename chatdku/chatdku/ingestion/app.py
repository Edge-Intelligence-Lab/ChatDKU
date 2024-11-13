import streamlit as st
from query import get_pipeline
from chatdku.setup import setup


# Define the main Streamlit interface function
def main():

    if "setup_done" not in st.session_state:
        print("0000" * 50)
        setup(add_system_prompt=True)
        st.session_state.setup_done = True

    if "pipeline" not in st.session_state:
        print("1111" * 50)
        st.session_state.pipeline = get_pipeline(
            retriever_type="vector",
            hyde=True,
            vector_top_k=5,
            bm25_top_k=5,
            fusion_top_k=5,
            num_queries=3,
            synthesize_response=True,
        )

    st.title("DKU LLM v1.0")
    st.info("powered by LlamaIndex 💬🦙")
    # Text box for user input
    query = st.text_input("Enter your query about DKU:")

    # Button to run the query
    if st.button("Get Response"):
        if query:  # If the query is not empty
            with st.spinner("Fetching response..."):
                # Run the pipeline with the user's query
                output = st.session_state.pipeline.run(input=query)

                st.text("Response:")
                print(output)
                st.write(output.response_txt)  # Display the response
        else:
            st.warning("Please enter a valid query.")


# Run the Streamlit app
if __name__ == "__main__":
    main()
