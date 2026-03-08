import subprocess
import json

def execute(action):

    process = subprocess.run(
        ["../rust-runtime/target/debug/rust-runtime"],
        input=json.dumps(action),
        text=True,
        capture_output=True
    )

    print("Rust executed:", action)