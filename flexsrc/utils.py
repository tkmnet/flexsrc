import requests

class FlexSrcUtils:
    def download(url, dst):
        req = requests.get(url, stream=True)
        with open(dst, 'wb') as f:
            for chunk in req.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()