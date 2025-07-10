"""
Module for loading data from various sources (e.g., files, folders).
"""


import os
from loguru import logger
from tqdm import tqdm


class DataLoader:
    def load(self, path):
        """
        Load data from a file or all .txt files in a directory.
        Returns a dict: {filename: content}
        """
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                return {os.path.basename(path): f.read()}
        elif os.path.isdir(path):
            data = {}
            for fname in tqdm(
                os.listdir(path), desc=(
                    f'Loading .txt files from {path}'
                )
            ):
                if fname.endswith('.txt'):
                    fpath = os.path.join(path, fname)
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data[fname] = f.read()
            return data
        else:
            raise FileNotFoundError(f"Path not found: {path}")

    def load_and_save(self, input_path, output_path):
        """Load text from input_path and save to output_path."""
        data = self.load(input_path)
        # data is a dict: {filename: content}
        for _, content in data.items():
            logger.info(
                f"Saving loaded content to {output_path}"
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content) 