import os
import json
import time
from datetime import datetime
from config import DATA_DIR, SCREENSHOT_DIR

AUDIT_LOG_FILE = os.path.join(DATA_DIR, "audit_logs.jsonl")

class AuditLogger:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        
    def log_event(self, action_name, screenshot_path=None, extracted_text=None, generated_response=None, success=True, error_msg=None, extra_data=None):
        """Log an agent interaction event for the UI dashboard.
        
        Args:
            action_name (str): Label for the action (e.g., 'Read Post', 'Comment')
            screenshot_path (str): Path to the image vision saw, if any.
            extracted_text (str): What was extracted from DOM/Vision.
            generated_response (str): What the AI generated in response.
            success (bool): Did the action succeed?
            error_msg (str): Error message if failure.
            extra_data (dict): Any other debug params.
        """
        event = {
            "id": f"evt_{int(time.time() * 1000)}",
            "timestamp": datetime.now().isoformat(),
            "action": action_name,
            "success": success,
        }
        
        # We only want relative paths for the dashboard to serve
        if screenshot_path and os.path.exists(screenshot_path):
            event["screenshot"] = os.path.basename(screenshot_path)
            
        if extracted_text is not None:
            event["extracted_text"] = extracted_text
            
        if generated_response is not None:
            event["generated_response"] = generated_response
            
        if error_msg:
            event["error"] = error_msg
            
        if extra_data:
            event["extra"] = extra_data
            
        try:
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"[Audit] Failed to write log: {e}")

# Global instance
audit_logger = AuditLogger()
