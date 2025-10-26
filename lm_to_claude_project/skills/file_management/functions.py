
import os

def list_files(directory='.'):
    """Lists files in a given directory."""
    return os.listdir(directory)

def read_file(path):
    """Reads the content of a file."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    """Writes content to a file."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
