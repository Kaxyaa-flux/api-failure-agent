from typing import List, Dict

def cluster_failures(logs: List[Dict]) -> List[Dict]:
    clusters = {}
    
    for log in logs:
        # Consider 4xx and 5xx status codes as failures
        if log["status_code"] >= 400:
            key = (log["endpoint"], log["status_code"])
            if key not in clusters:
                clusters[key] = {
                    "endpoint": log["endpoint"],
                    "status_code": log["status_code"],
                    "count": 0
                }
            clusters[key]["count"] += 1
            
    return list(clusters.values())
