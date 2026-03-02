import subprocess
import tempfile
import os

def render_mermaid_to_png(mermaid_code: str) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mmd") as input_file:
        input_file.write(mermaid_code.encode("utf-8"))
        input_path = input_file.name

    output_path = input_path.replace(".mmd", ".png")

    try:
        # Run Mermaid CLI
        result = subprocess.run(
    [r"C:\Users\user\AppData\Roaming\npm\mmdc.cmd", "-i", input_path, "-o", output_path],
    capture_output=True,
    text=True,
    shell=True
)

        # Debug output
        print("==== Mermaid CLI STDOUT ====")
        print(result.stdout)
        print("==== Mermaid CLI STDERR ====")
        print(result.stderr)

        # If CLI failed, raise error with real reason
        if result.returncode != 0:
            raise Exception(f"Mermaid CLI failed:\n{result.stderr}")

        # Read generated PNG
        with open(output_path, "rb") as f:
            png_bytes = f.read()

    finally:
        # Cleanup temp files
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

    return png_bytes