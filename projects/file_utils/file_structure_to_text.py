import os

def generate_tree(startpath, display_root="project_root", output_file="tree_structure.txt"):
    lines = []

    def tree(dir_path, prefix=""):
        entries = sorted(os.listdir(dir_path))
        entries_count = len(entries)

        for index, entry in enumerate(entries):
            path = os.path.join(dir_path, entry)
            is_dir = os.path.isdir(path)
            connector = "└── " if index == entries_count - 1 else "├── "
            suffix = "/" if is_dir else ""
            # Skip __pycache__ folder
            if is_dir:
                if entry in ["__pycache__",".git","old",".venv",".vscode","gspy.egg-info"]:
                    continue
            elif entry in ["file_structure_to_text.py",".gitignore"]:
                continue
            lines.append(prefix + connector + entry + suffix)
            if is_dir:
                if entry == "__pycache__":
                    extension = "    " if index == entries_count - 1 else "│   "
                    lines.append(prefix + extension + "└── ...")
                    continue

                extension = "    " if index == entries_count - 1 else "│   "
                tree(path, prefix + extension)

    lines.append(f"{display_root}/")
    tree(startpath)

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Tree structure saved to '{output_file}'")
    
# Example usage:
generate_tree(".")