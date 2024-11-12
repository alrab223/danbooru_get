import requests


def download_image(image_url, image_path):
   response = requests.get(image_url)
   if response.status_code == 200:
      with open(image_path, "wb") as f:
         f.write(response.content)
