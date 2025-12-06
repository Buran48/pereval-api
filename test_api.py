import requests
import json

url = "http://localhost:8001/submitData"
headers = {
    "accept": "application/json",
    "Content-Type": "application/json"
}

data = {
    "beauty_title": "pereval",
    "title": "test pereval",
    "other_titles": "test",
    "connect": "connects",
    "add_time": "2023-12-06 10:30:00",
    "user": {
        "email": "test@mail.ru",
        "fam": "mishin",
        "name": "misha",
        "otc": "mikhailovich",
        "phone": "123456789"
    },
    "coords": {
        "latitude": "55.7558",
        "longitude": "37.6176",
        "height": "200"
    },
    "level": {
        "winter": "1A",
        "summer": "1B",
        "autumn": "1A",
        "spring": ""
    },
    "images": [
        {
            "data": "test_image",
            "title": "view"
        }
    ]
}

response = requests.post(url, headers=headers, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")