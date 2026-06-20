import sys
import os
import requests
from io import BytesIO
from PIL import Image

def generate_test_image():
    # Generate a simple 100x100 white square image
    img = Image.new('RGB', (100, 100), color = 'white')
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def run_test():
    base_url = "http://127.0.0.1:8000"
    
    # 1. Health check
    print("1. Checking API Health...")
    try:
        r = requests.get(f"{base_url}/api/health")
        r.raise_for_status()
        print("API Health Response:", r.json())
    except Exception as e:
        print(f"Error connecting to backend: {e}")
        print("Please make sure the backend server is running on http://127.0.0.1:8000")
        sys.exit(1)
        
    # 2. Upload file
    print("\n2. Uploading test receipt to trigger Swiggy mock OCR...")
    img_data = generate_test_image()
    
    # We name the file 'swiggy_test_receipt.png' to trigger the Swiggy mock template in OCR engine
    files = {
        'file': ('swiggy_test_receipt.png', img_data, 'image/png')
    }
    
    try:
        r = requests.post(f"{base_url}/api/upload", files=files)
        if r.status_code != 201:
            print(f"Upload failed: Code {r.status_code}, Detail: {r.text}")
            sys.exit(1)
        
        result = r.json()
        print("Upload Successful! Response:")
        print(f"  Expense ID: {result['expense']['id']}")
        print(f"  Merchant: {result['expense']['merchant']}")
        print(f"  Amount: Rs. {result['expense']['amount']}")
        print(f"  Category: {result['expense']['category']}")
        print(f"  Raw Text Sample:\n---\n{result['receipt']['raw_text']}\n---")
        
        expense_id = result['expense']['id']
    except Exception as e:
        print(f"Upload request failed: {e}")
        sys.exit(1)
        
    # 3. Retrieve all expenses
    print("\n3. Listing all expenses in database...")
    try:
        r = requests.get(f"{base_url}/api/expenses")
        r.raise_for_status()
        expenses = r.json()
        print(f"Found {len(expenses)} expenses in database.")
        for exp in expenses:
            print(f"  - [{exp['id']}] {exp['merchant']}: Rs. {exp['amount']} ({exp['category']})")
    except Exception as e:
        print(f"Failed to fetch expenses: {e}")
        sys.exit(1)

    # 4. Try updating the expense (Simulate the 'verify and correct' flow)
    print(f"\n4. Correcting expense details for ID {expense_id}...")
    try:
        # Correct Swiggy to "Swiggy (Bundl Technologies)" and update amount
        payload = {
            "merchant": "Swiggy (Bundl Technologies)",
            "amount": 350.00,
            "category": "Food & Dining"
        }
        r = requests.put(f"{base_url}/api/expenses/{expense_id}", json=payload)
        r.raise_for_status()
        updated = r.json()
        print("Update Successful! Response:")
        print(f"  Merchant: {updated['merchant']}")
        print(f"  Amount: Rs. {updated['amount']}")
        print(f"  Category: {updated['category']}")
    except Exception as e:
        print(f"Failed to update expense: {e}")
        sys.exit(1)

    print("\nAll Month 1 backend tests completed successfully!")

if __name__ == "__main__":
    run_test()
