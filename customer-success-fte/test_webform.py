import httpx
import asyncio
import json

async def test_submission():
    url = "http://localhost:8000/api/v1/channels/webform/submit"
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "subject": "Missing order #12345",
        "message": "I haven't received my order yet. Help!",
        "priority": "high",
        "metadata": {"test": True}
    }
    
    print(f"Submitting to {url}...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_submission())
