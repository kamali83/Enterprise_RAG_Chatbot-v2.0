import os

def get_all_files(directory: str):
    """Get all file paths in a directory."""
    if not os.path.exists(directory):
        os.makedirs(directory)
    return [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
