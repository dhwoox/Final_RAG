
import json
import re
import os

# Note: This skill requires chromadb, langchain_chroma, and langchain_huggingface to be installed.
# pip install chromadb langchain_chroma langchain_huggingface sentence_transformers

# These imports are wrapped inside the function to avoid breaking the agent 
# if these libraries are not installed, as they are specific to this skill.

def get_test_case_details(test_case_id: str) -> str:
    """
    Retrieves test case details from a ChromaDB database based on an ID string.
    """
    try:
        import chromadb
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        return json.dumps({"error": "Required libraries (chromadb, langchain) are not installed."})

    # --- Configuration ---
    db_path = "/Users/admin/Documents/2025_project/QE_RAG_COMPANY/QE_RAG_2025/chroma_db"
    collection_name = "jira_test_cases"
    embedding_model = "intfloat/multilingual-e5-large"

    # --- 1. Parse the test_case_id string ---
    issue_key_match = re.search(r'(COMMONR-\d+)', test_case_id)
    step_number_match = re.search(r'스텝\s*(\d+)_(\d+)', test_case_id)
    step_index_match = re.search(r'스텝\s*(\d+)', test_case_id)
    step_of_number_match = re.search(r'스텝\s*(\d+).*?(\d+)번', test_case_id)

    if not issue_key_match:
        return json.dumps({"error": f"Could not find issue key like 'COMMONR-XX' in query: {test_case_id}"})

    issue_key = issue_key_match.group(1)
    step_index = None

    if step_number_match:
        step_index = step_number_match.group(1)
    elif step_of_number_match:
        step_index = step_of_number_match.group(1)
    elif step_index_match:
        step_index = step_index_match.group(1)

    # --- 2. Connect to ChromaDB and retrieve data ---
    try:
        # Embedding function setup
        model_kwargs = {'device': 'cpu', 'trust_remote_code': True}
        encode_kwargs = {'normalize_embeddings': True, 'batch_size': 1}
        embedding_function = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )

        # Connect to the vectorstore
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embedding_function,
            persist_directory=db_path
        )

        # Construct the metadata filter
        if step_index:
            where_filter = {
                "$and": [
                    {"issue_key": {"$eq": issue_key}},
                    {"step_index": {"$eq": step_index}}
                ]
            }
        else:
            where_filter = {"issue_key": {"$eq": issue_key}}

        # Perform the metadata-based search
        collection = vectorstore.get(where=where_filter)

        if not collection or not collection.get('ids'):
            return json.dumps({"error": f"No test case found for filter: {where_filter}"})

        # --- 3. Format and return the results ---
        results = []
        ids = collection.get('ids', [])
        documents = collection.get('documents', [])
        metadatas = collection.get('metadatas', [])

        for i in range(len(ids)):
            results.append({
                "content": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
            })
        
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"An error occurred while querying the database: {str(e)}"})
