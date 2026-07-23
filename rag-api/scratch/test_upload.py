import urllib.request
import urllib.error
import mimetypes

url = "http://localhost:8000/ingest"
filename = "dummy.txt"
file_data = b"Hello world. " * 1000000  # ~12MB

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = []

# Build multipart/form-data
body.append(f"--{boundary}".encode('utf-8'))
body.append(f'Content-Disposition: form-data; name="files"; filename="{filename}"'.encode('utf-8'))
body.append(f"Content-Type: text/plain".encode('utf-8'))
body.append(b"")
body.append(file_data)
body.append(f"--{boundary}--".encode('utf-8'))
body.append(b"")

payload = b"\r\n".join(body)

headers = {
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    "Content-Length": str(len(payload))
}

req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

print(f"Uploading {len(payload) / (1024*1024):.2f} MB to {url}...")
try:
    with urllib.request.urlopen(req) as response:
        print("Response status code:", response.status)
        print("Response body:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error status code:", e.code)
    print("HTTP Error response body:", e.read().decode('utf-8'))
except Exception as e:
    print("Connection error:", e)
