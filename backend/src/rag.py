from rag_core import answer_question

# ==========================================
# Main Loop
# ==========================================

def main():

    print("\nInstitutional Knowledge Retrieval System")
    print("Type 'exit' to quit.\n")

    while True:

        question = input("Ask a question: ")

        if question.lower() == "exit":
            print("Goodbye!")
            break

        result = answer_question(question)

        print("\nAnswer:")
        print(result["answer"])

        print("\nSources:")
        for source in result["sources"]:
            print(f"- {source}")

        print("\n" + "=" * 80 + "\n")
       


if __name__ == "__main__":
    main()