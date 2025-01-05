import aiohttp
import asyncio
import time
import rsa
from pathlib import Path

CONSUMER_ID = ""
KEY_VERSION = "1"
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
-----END RSA PRIVATE KEY-----"""
API_URL = "https://developer.api.walmart.com/api-proxy/service/affil/product/v2/items/{sku}?storeId={store_ID}"

def generate_signature(consumer_id, timestamp, key_version):
    private_key = rsa.PrivateKey.load_pkcs1(PRIVATE_KEY.encode("utf-8"))
    payload = f"{consumer_id}\n{timestamp}\n{key_version}\n"
    signature = rsa.sign(payload.encode("utf-8"), private_key, "SHA-256")
    return signature.hex()

def generate_headers_once():
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(CONSUMER_ID, timestamp, KEY_VERSION)
    headers = {
        "WM_SEC.KEY_VERSION": KEY_VERSION,
        "WM_CONSUMER.ID": CONSUMER_ID,
        "WM_CONSUMER.INTIMESTAMP": timestamp,
        "WM_SEC.AUTH_SIGNATURE": signature,
    }
    print("Generated Headers:", headers)
    return headers

def read_store_ids(file_path):
    try:
        with open(file_path, "r") as file:
            lines = file.readlines()
        store_ids = [line.split(":")[1].strip() for line in lines if line.startswith("Store ID")]
        return store_ids
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return []

async def fetch_price(session, sku, store_id, headers):
    url = API_URL.format(sku=sku, store_ID=store_id)
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                price = data.get("price", {}).get("priceInCents", None)
                stock_status = data.get("inventoryStatus", {}).get("stockStatus", "Unknown")
                if price is not None:
                    price_dollars = price / 100
                    return {"store_id": store_id, "price": price_dollars, "stock_status": stock_status}
            else:
                print(f"Error {response.status} for Store ID {store_id}: {await response.text()}")
    except Exception as e:
        print(f"Error fetching {sku} from store {store_id}: {e}")
    return None

async def scrape_prices(sku, store_ids):
    headers = generate_headers_once()
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_price(session, sku, store_id, headers) for store_id in store_ids]
        responses = await asyncio.gather(*tasks)
        results = [res for res in responses if res]

    results.sort(key=lambda x: x["price"])

    if results:
        lowest_price = results[0]["price"]
        print(f"Lowest Price:\n${lowest_price:.2f}\n")
        print("Sorted Entries (Lowest to Highest Price) with URLs:")
        for res in results:
            store_id = res["store_id"]
            price = res["price"]
            stock_status = res["stock_status"]
            url = f"https://www.walmart.com/ip/{sku}/?wl13={store_id}"
            print(f"${price:.2f} - {store_id} - {stock_status}: {url}")

        output_file = f"{sku}_{lowest_price}_results.txt"
        with open(output_file, "w") as file:
            for res in results:
                store_id = res["store_id"]
                price = res["price"]
                stock_status = res["stock_status"]
                url = f"https://www.walmart.com/ip/{sku}/?wl13={store_id}"
                file.write(f"${price:.2f} - {store_id} - {stock_status}: {url}\n")
        print(f"\nResults saved to {output_file}")
    else:
        print("No results found.")

if __name__ == "__main__":
    store_ids_file = "store_ids.txt"
    store_ids = read_store_ids(store_ids_file)

    if not store_ids:
        print("No store IDs found. Please check the store_ids.txt file.")
    else:
        sku = input("Enter SKU: ")
        asyncio.run(scrape_prices(sku, store_ids))


# NO CLUE IF THIS SHIT IS FIXABLE BUT YEAH