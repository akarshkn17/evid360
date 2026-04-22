#!/usr/bin/env python3

import json
import requests
from requests.auth import HTTPBasicAuth

# ==============================
# 🔧 CONFIG (EDIT HERE ONLY)
# ==============================

JIRA_BASE_URL = "https://sai360.atlassian.net"
JIRA_EMAIL = "your-email@example.com"
JIRA_API_TOKEN = "your-api-token"

SCHEMA_ID = 4
OBJECT_TYPE_ID = 34

AQL_QUERY = f"objectTypeId = {OBJECT_TYPE_ID}"
INCLUDE_ATTRIBUTES = True
OUTPUT_FILE = "assets_output.json"

# ==============================
# 🚀 SCRIPT START
# ==============================


class JiraAssetsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        self.workspace_id = None

    def get_workspace_id(self):
        url = f"{JIRA_BASE_URL}/rest/servicedeskapi/assets/workspace"
        resp = self.session.get(url)
        resp.raise_for_status()

        data = resp.json()
        self.workspace_id = data["values"][0]["workspaceId"]
        print(f"[+] Workspace ID: {self.workspace_id}")

    def get_schema(self):
        url = f"{JIRA_BASE_URL}/gateway/api/jsm/assets/workspace/{self.workspace_id}/v1/objectschema/{SCHEMA_ID}"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_object_type(self):
        url = f"{JIRA_BASE_URL}/gateway/api/jsm/assets/workspace/{self.workspace_id}/v1/objecttype/{OBJECT_TYPE_ID}"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def fetch_assets(self):
        all_objects = []
        start_at = 0
        max_results = 100

        while True:
            url = f"{JIRA_BASE_URL}/gateway/api/jsm/assets/workspace/{self.workspace_id}/v1/object/aql"

            params = {
                "startAt": start_at,
                "maxResults": max_results,
                "includeAttributes": str(INCLUDE_ATTRIBUTES).lower()
            }

            payload = {
                "qlQuery": AQL_QUERY
            }

            resp = self.session.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

            values = data.get("values", [])
            if not values:
                break

            all_objects.extend(values)

            print(f"[+] Fetched {len(all_objects)} objects so far...")

            if data.get("isLastPage", False):
                break

            start_at += len(values)

        return all_objects


def main():
    fetcher = JiraAssetsFetcher()

    print("[*] Getting workspace...")
    fetcher.get_workspace_id()

    print("[*] Fetching schema metadata...")
    schema = fetcher.get_schema()

    print("[*] Fetching object type metadata...")
    obj_type = fetcher.get_object_type()

    print("[*] Fetching assets...")
    objects = fetcher.fetch_assets()

    result = {
        "schemaId": SCHEMA_ID,
        "objectTypeId": OBJECT_TYPE_ID,
        "aql": AQL_QUERY,
        "count": len(objects),
        "schema": schema,
        "objectType": obj_type,
        "objects": objects
    }

    print(f"[+] Total objects fetched: {len(objects)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[+] Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()