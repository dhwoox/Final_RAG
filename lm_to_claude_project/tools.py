import os
import subprocess

def skill_retriever(query: str) -> str:
    """
    Finds the most relevant skill from the 'skills' directory based on the user's query.
    For simplicity, this example uses keyword matching. For a more advanced system,
    consider using vector search (e.g., ChromaDB, FAISS).
    """
    skills_dir = os.path.join(os.path.dirname(__file__), 'skills')
    best_skill = None
    highest_score = 0

    for skill_name in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, skill_name)
        if os.path.isdir(skill_path):
            instructions_path = os.path.join(skill_path, 'instructions.md')
            if os.path.exists(instructions_path):
                with open(instructions_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    score = sum(keyword in content for keyword in query.lower().split())
                    if score > highest_score:
                        highest_score = score
                        best_skill = skill_name

    if not best_skill:
        return "No relevant skill found."

    # Return the content of the found skill's directory
    skill_content = ""
    skill_path = os.path.join(skills_dir, best_skill)
    for filename in ['instructions.md', 'functions.py']:
        filepath = os.path.join(skill_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                skill_content += f"--- {filename} ---\n{f.read()}\n\n"
    
    return skill_content

def python_executor(code: str) -> str:
    """
    Executes a given string of Python code and returns the output.
    WARNING: This tool executes code on the local machine. It is a security risk
    and should only be used in a sandboxed environment.
    """
    try:
        # It's safer to write to a temporary file and execute it
        with open("_temp_execution.py", "w", encoding="utf-8") as f:
            f.write(code)
        
        result = subprocess.run(
            ["python", "_temp_execution.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        os.remove("_temp_execution.py")

        if result.returncode == 0:
            return f"Execution successful:\nStdout:\n{result.stdout}"
        else:
            return f"Execution failed:\nStderr:\n{result.stderr}"
    except Exception as e:
        return f"An error occurred during execution: {str(e)}"

# You can add other general-purpose tools here
def list_files(directory: str ='.') -> str:
    """Lists files in a given directory."""
    try:
        files = os.listdir(directory)
        return "\n".join(files)
    except Exception as e:
        return str(e)
