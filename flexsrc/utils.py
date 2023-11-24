import os
import requests
import uuid
import shutil

class FlexSrcUtils:
    def download(url, dst):
        req = requests.get(url, stream=True)
        with open(dst, 'wb') as f:
            for chunk in req.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
    
    def unarchive(url):
        tmp_file = str(uuid.uuid4())
        FlexSrcUtils.download(url, tmp_file)
        shutil.unpack_archive(tmp_file, '.')
        os.remove(tmp_file)
        
