import os
import json
import urllib.request

def generate_explanation(anomaly):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if api_key:
        try:
            # Simple direct API call using standard library to avoid extra dependencies
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            prompt = f"Analyze this API anomaly and provide a JSON response:\\n{json.dumps(anomaly, indent=2)}\\n\\nFormat your response as a valid JSON object with the following keys: 'issue' (string), 'severity' (string: high/medium/low), 'confidence' (float 0-1), 'root_cause' (string), 'steps' (list of strings)."
            
            data = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["content"][0]["text"]
                
                # Extract JSON from response
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                return json.loads(content)
        except Exception as e:
            print(f"LLM API Error: {e}")
            # Fallback to mock on error
            pass
            
    # Mock fallback
    return get_mock_explanation(anomaly)

def get_mock_explanation(anomaly):
    # Determine severity based on anomaly data
    severity = "low"
    if anomaly.get("error_rate", 0) > 0.5:
        severity = "high"
    elif anomaly.get("error_rate", 0) > 0.2:
        severity = "medium"
    elif anomaly.get("latest_latency", 0) > anomaly.get("avg_latency", 0) * 3:
        severity = "medium"
        
    issue_type = f"High error rate ({anomaly.get('error_rate', 0)*100:.1f}%) detected" if anomaly.get("error_rate", 0) > 0.2 else f"Latency spike ({anomaly.get('latest_latency', 0)}ms) detected"
    root_cause = "Database connection pool exhausted" if severity == "high" else "Unoptimized database query or cache miss"
    
    return {
        "issue": f"{issue_type} on {anomaly.get('endpoint', 'unknown endpoint')}",
        "severity": severity,
        "confidence": 0.85,
        "root_cause": root_cause,
        "steps": [
            "Check database active connections",
            "Review recent deployments or configuration changes",
            "Scale up the database instance if necessary"
        ]
    }
