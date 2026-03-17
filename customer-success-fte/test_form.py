import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            'http://localhost:8000/api/v1/channels/webform/submit',
            json={
                'name': 'Amna Test',
                'email': 'amna@test.com',
                'subject': 'Testing from Dell laptop',
                'category': 'technical',
                'message': 'End to end test from Dell E5470'
            }
        )
        print('Status:', r.status_code)
        try:
            print('Response:', r.json())
        except Exception:
            print('Response:', r.text)

asyncio.run(test())
