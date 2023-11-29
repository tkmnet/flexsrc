from pathlib import Path
import shutil
from flexsrc import FlexSrcLeaf

class FSFilePath(Path):
    _flavour = type(Path())._flavour

    def put(self, dst=None):
        if dst is None:
            dst = self.name
        shutil.copy(self, dst)
        return dst
    
    def open():
        return open(self, 'r')


class FlexSrcFile(FlexSrcLeaf):
    def __init__(self, target, params={}) -> None:
        if isinstance(target, Path):
            self.target = target
        else:
            super().__init__(target, params)
    
    def get_body(self):
        if isinstance(self.target, Path):
            return FSFilePath(self.target)
        else:
            return FSFilePath(Path(super().get_body()))