import subprocess
import json
import os
import tempfile
from pathlib import Path

# Path to the self-healing directory
SELF_HEALING_DIR = Path(__file__).parent / "self-healing"

def heal_selector(intent, html_content, error_message="Timeout Error"):
    """
    Bridge to the TypeScript self-healing CLI.
    
    Args:
        intent (str): The logical intent (e.g., "Click Connect Button")
        html_content (str): The current page HTML
        error_message (str): The error encountered
        
    Returns:
        dict: The healing result (e.g., {"status": "fixed", "newSelector": ".css-123"})
    """
    print(f"[Self-Healing Bridge] Attempting to heal: {intent}")
    
    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
        tmp.write(html_content)
        tmp_path = tmp.name
        
    try:
        # Run the TypeScript CLI
        # Use npx ts-node to run the CLI
        cmd = [
            "npx", "ts-node", "src/cli.ts",
            intent,
            tmp_path,
            error_message
        ]
        
        result = subprocess.run(
            cmd,
            cwd=SELF_HEALING_DIR,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the output
        output = result.stdout.strip()
        # Find the JSON part in case of any extra logs
        import re
        json_match = re.search(r'\{.*\}', output)
        if json_match:
            return json.loads(json_match.group(0))
        
        print(f"[Self-Healing Bridge] Could not parse JSON. Output: {output}")
        if result.stderr:
            print(f"[Self-Healing Bridge] STDERR: {result.stderr}")
        return {"status": "failed", "newSelector": ""}
        
    except subprocess.CalledProcessError as e:
        print(f"[Self-Healing Bridge] Subprocess Error: {e}")
        print(f"[Self-Healing Bridge] STDOUT: {e.stdout}")
        print(f"[Self-Healing Bridge] STDERR: {e.stderr}")
        return {"status": "failed", "newSelector": ""}
    except Exception as e:
        print(f"[Self-Healing Bridge] Error: {e}")
        return {"status": "failed", "newSelector": ""}
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    # Test the bridge
    test_html = "<html><body><button id='real-btn'>Click Me</button></body></html>"
    res = heal_selector("Click the button", test_html)
    print(f"Result: {res}")
