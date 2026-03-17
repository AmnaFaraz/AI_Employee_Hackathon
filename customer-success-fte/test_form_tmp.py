import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post('http://localhost:8000/support/submit', json={
                'name': 'Amna Test',
                'email': 'amna@test.com',
                'subject': 'Testing from Dell laptop',
                'category': 'technical',
                'message': 'End to end test from Dell E5470'
            })
            print('Status:', r.status_code)
            try:
                print('Response:', r.json())
            except Exception as e:
                print('Response (text):', r.text)
        except Exception as e:
            print('Error during request:', e)

if __name__ == "__main__":
    asyncio.run(test())
