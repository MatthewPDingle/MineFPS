import os

def main():
    script_name = os.path.basename(__file__)
    output_filename = "unify.txt"

    with open(output_filename, 'w', encoding='utf-8') as out_file:
        for filename in os.listdir('.'):
            if filename.endswith('.py') and filename != script_name and os.path.isfile(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    contents = f.read()
                out_file.write(f"<{filename}>\n")
                out_file.write(contents)
                out_file.write(f"\n</{filename}>\n\n")

if __name__ == "__main__":
    main()