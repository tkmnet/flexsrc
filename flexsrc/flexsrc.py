import os
import sys
import tempfile
from typing import Any
from pathlib import Path
import copy
import json
import shutil
import yaml
import xxhash
import cfcf

FLEXSRC = 'FlexSrc'
FSR_FILE = '__flexsrc__.yaml'
FSR_EXT = '.flexsrc.yaml'
CONFIG_FILE = 'flexsrc.conf'
REPO_CACHE_DIR = 'repo_cache_dir'
DATA_CACHE_DIR = 'data_cache_dir'
CACHE_PATH = 'cache_path'
OBJECT_LOADER = 'object_loader'
OBJECT_LOADER_PATH = 'object_loader_path'
DEFAULT_OBJECT_LOADER = '__flexsrc__.py'
LOCAL = 'local'
IS_LOCAL = 'is_local'
PATH = 'path'
FLEXSRC_CURRENT_ROOT_DIR = 'flexsrc_current_root_dir'
FLEXSRC_CURRENT_TARGET_NAME = 'flexsrc_current_target_name'
WORK_DIR = 'work_dir'
PARAMS = 'params'
CONFIGS = 'configs'
TAIL = 'tail'
STORAGE = 'storage'
DEFAULT_PARAMS = 'default_params'
OBJECTS_FUNC = 'objects_func'
DEFAULT_OBJECTS_FUNC = 'objects'
INFO = 'info'
DATA = 'data'
REPO = 'repo'
ID = 'id'
REPO_CACHE = 'repo_cache'


def get_file_contents(path):
    res = None
    if os.path.isfile(path):
        with open(path, 'r') as file:
            res = file.read()
    return res


def to_object_from_yaml(text):
    if text is not None:
        try:
            obj = yaml.safe_load(text)
            if isinstance(obj, dict):
                return obj
        except Exception as e:
            print(e, file=sys.stderr)
    return {}


def filter_dot_keys(obj):
    res = {}
    for k, v in obj.items():
        if not k.startswith('.'):
            res[k] = v
    return res


class FSIndirectObject(dict):
    def __init__(self, obj):
        self.update(obj)

    def __exit__(self, *args):
        self.clear()

    def __getitem__(self, __key: Any) -> Any:
        if isinstance(__key, list):
            __key = copy.deepcopy(__key)
            obj = self
            while len(__key) > 0:
                if isinstance(obj, FlexSrc):
                    obj.tail = copy.deepcopy(__key)
                key = __key.pop(0)
                obj = obj[key]
        else:
            obj = super().__getitem__(__key)
        if isinstance(obj, FlexSrcLeaf):
            return obj.get_body()
        elif isinstance(obj, FlexSrc):
            return obj
        elif isinstance(obj, dict):
            return FSIndirectObject(obj)
        return obj
    
    def __getattr__(self, __name: str) -> Any:
        return self.__getitem__(__name)


class FSParams(dict):
    def __init__(self, holder, obj):
        self.holder = holder
        self.initialized = False
        self.loaded_default = {}
        if len(obj) > 0:
            self.initialize()
        self.update(obj)

    def get_changed(self):
        changed = {}
        for k, v in self.items():
            if k in self.loaded_default:
                if v != self.loaded_default[k]:
                    changed[k] = v
            else:
                changed[k] = v
        return changed

    def __str__(self) -> str:
        self.initialize()
        return super().__repr__()

    def __repr__(self) -> str:
        changed = filter_dot_keys(self.get_changed())
        return '' if len(changed) <= 0 else repr(changed)

    def __call__(self):
        print(json.dumps(self, indent=2))
        return self

    def initialize(self):
        if not self.initialized:
            self.initialized = True
            self.holder.load_params(self)
            self.loaded_default.clear()
            self.loaded_default.update(self)


class InvalidFlexSrc(RuntimeError):
    pass


class FlexSrc(FSIndirectObject):
    def __init__(self, target, params={}, tail=[]):
        pre_load = True
        root_dir = None
        self.target = target
        self.forced_objects_func = None
        self.target_name = target
        self.flexsrc_id = ''
        if callable(target):
            self.target = '.'
            self.forced_objects_func = target.__name__
            self.target_name = f"{globals()[FLEXSRC_CURRENT_TARGET_NAME]}.{target.__name__}"
        if root_dir is None:
            if FLEXSRC_CURRENT_ROOT_DIR in globals():
                root_dir = globals()[FLEXSRC_CURRENT_ROOT_DIR]
                pre_load = False
            else:
                root_dir = os.getcwd()
        self.root_dir = root_dir
        self.is_cached_repo = False
        self.is_config_loaded = False
        self.loaded_params_str = None
        self.configs = {
            REPO_CACHE_DIR: None,
            DATA_CACHE_DIR: None,
            OBJECT_LOADER: DEFAULT_OBJECT_LOADER,
            DEFAULT_PARAMS: {},
            OBJECTS_FUNC: DEFAULT_OBJECTS_FUNC,
            INFO: None
        }
        self.params = FSParams(self, params)
        self.tail = tail
        self.storage = {}
        if pre_load:
            self.load()

    def __str__(self) -> str:
        self.load()
        return f"{self.__class__.__name__}({self.target_name}{repr(self.params)}): {super().__repr__()}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.target_name}{repr(self.params)})"

    def __getitem__(self, __key: Any) -> Any:
        self.load()
        return super().__getitem__(__key)

    def __call__(self):
        self.load()
        print(repr(self))
        is_first = True
        print('{', end='')
        for k, v in self.items():
            if is_first:
                is_first = False
                print(f"\n  \"{k}\": {repr(v)}", end='')
            else:
                print(f",\n  \"{k}\": {repr(v)}", end='')
        print('\n}')
        return self

    def try_load_configs(self):
        self.configs.update(to_object_from_yaml(get_file_contents(
          Path(os.path.expanduser('~')) / ('.' + CONFIG_FILE))))
        self.configs.update(to_object_from_yaml(get_file_contents(
          Path(os.path.expanduser('~')) / CONFIG_FILE)))
        self.configs.update(to_object_from_yaml(
          get_file_contents('.' + CONFIG_FILE)))
        self.configs.update(to_object_from_yaml(
          get_file_contents(CONFIG_FILE)))

    def prepare_cache_dir(self):
        if self.configs[REPO_CACHE_DIR] is None:
            with tempfile.TemporaryDirectory() as d:
                self.configs[REPO_CACHE_DIR] =\
                  Path(d).parent / FLEXSRC / REPO
        if self.configs[DATA_CACHE_DIR] is None:
            with tempfile.TemporaryDirectory() as d:
                self.configs[DATA_CACHE_DIR] =\
                  Path(d).parent / FLEXSRC / DATA
        os.makedirs(self.configs[REPO_CACHE_DIR], exist_ok=True)
        os.makedirs(self.configs[DATA_CACHE_DIR], exist_ok=True)

    def try_load_flexsrc_yaml(self):
        flexsrc_yaml = '{}'
        if cfcf.chdir_and_call(self.configs[REPO_CACHE_DIR],
                               lambda: cfcf.exist(Path(self.root_dir) / self.target / FSR_FILE)):
            self.is_cached_repo = True
            self.flexsrc_yaml_path = Path(self.root_dir) / self.target / FSR_FILE
            self.flexsrc_yaml_path = cfcf.chdir_and_call(self.configs[REPO_CACHE_DIR],
                                                         lambda: cfcf.get_file(self.flexsrc_yaml_path, cfcf.copy, self.flexsrc_yaml_path))
            self.configs[PATH] = Path(self.root_dir) / self.target
        elif cfcf.chdir_and_call(self.configs[REPO_CACHE_DIR],
                                 lambda: cfcf.exist(Path(self.root_dir) / (self.target + FSR_EXT))):
            self.is_cached_repo = True
            self.flexsrc_yaml_path = Path(self.root_dir) / (self.target + FSR_EXT)
            self.flexsrc_yaml_path = cfcf.chdir_and_call(self.configs[REPO_CACHE_DIR],
                                                         lambda: cfcf.get_file(self.flexsrc_yaml_path, cfcf.copy, self.flexsrc_yaml_path))
            self.configs[PATH] = Path(self.root_dir)
        elif os.path.isfile(Path(self.root_dir) / self.target / FSR_FILE):
            self.flexsrc_yaml_path = Path(self.root_dir) / self.target / FSR_FILE
            self.configs[PATH] = Path(self.root_dir) / self.target
        elif os.path.isfile(Path(self.root_dir) / (self.target + FSR_EXT)):
            self.flexsrc_yaml_path = Path(self.root_dir) / (self.target + FSR_EXT)
            self.configs[PATH] = Path(self.root_dir)
        else:
            raise InvalidFlexSrc(str(self.root_dir))
        self.configs.update(to_object_from_yaml(get_file_contents(self.flexsrc_yaml_path)))
        if ID in self.configs:
            self.flexsrc_id = self.configs[ID]
        else:
            self.flexsrc_id = xxhash.xxh32(self.configs[OBJECT_LOADER]).hexdigest()
        self.configs[IS_LOCAL] = True
        if self.configs[IS_LOCAL]:
            self.configs[CACHE_PATH] = Path(LOCAL) / f"{self.target_name}-{self.flexsrc_id}"
        else:
            pass #
        if not self.is_cached_repo and REPO_CACHE in self.configs and self.configs[REPO_CACHE]:
            self.is_cached_repo = True
            if self.configs[IS_LOCAL]:
                self.flexsrc_yaml_path = cfcf.chdir_and_call(self.configs[REPO_CACHE_DIR],
                                                             lambda: cfcf.get_file(self.flexsrc_yaml_path, cfcf.copy, self.flexsrc_yaml_path))

    def arrange_configs(self):
        c = self.configs
        c[WORK_DIR] = c[DATA_CACHE_DIR] / c[CACHE_PATH]
        c[OBJECT_LOADER_PATH] = c[PATH] / c[OBJECT_LOADER]
        if self.is_cached_repo:
            c[OBJECT_LOADER_PATH] = cfcf.chdir_and_call(self.configs[REPO_CACHE_DIR],
                                                             lambda: cfcf.get_file(c[OBJECT_LOADER_PATH], cfcf.copy, c[OBJECT_LOADER_PATH]))

        if self.forced_objects_func is not None:
            c[OBJECTS_FUNC] = self.forced_objects_func

    def load_config(self):
        if not self.is_config_loaded:
            self.is_config_loaded = True
            self.try_load_configs()
            self.prepare_cache_dir()
            self.try_load_flexsrc_yaml()
            self.arrange_configs()

    def load_params(self, storage):
        self.load_config()
        storage.update(self.configs[DEFAULT_PARAMS])
    
    def clean_cache(self):
        if os.path.isdir(self.configs[REPO_CACHE_DIR]):
            shutil.rmtree(self.configs[REPO_CACHE_DIR])
        if os.path.isdir(self.configs[DATA_CACHE_DIR]):
            shutil.rmtree(self.configs[DATA_CACHE_DIR])
        os.makedirs(self.configs[REPO_CACHE_DIR], exist_ok=True)
        os.makedirs(self.configs[DATA_CACHE_DIR], exist_ok=True)
        self.clear()

    def clear(self) -> None:
        self.loaded_params_str = None
        self.storage = {}
        return super().clear()

    def info(self):
        self.load_config()
        return self.configs[INFO]

    def load(self):
        params_str = str(self.params)
        if self.loaded_params_str != params_str:
            self.load_config()
            self.loaded_params_str = params_str
            # BEGIN: chdir
            cwd = os.getcwd()
            try:
                os.makedirs(self.configs[WORK_DIR], exist_ok=True)
                os.chdir(self.configs[WORK_DIR])
                # BEGIN: arrange globals
                globals()[FLEXSRC_CURRENT_ROOT_DIR] = self.configs[PATH]
                globals()[FLEXSRC_CURRENT_TARGET_NAME] = self.target_name
                # BEGIN: reflect objects
                sys.path.append(self.configs[PATH])
                code = compile(
                        get_file_contents(
                        self.configs[OBJECT_LOADER_PATH]),
                        self.configs[OBJECT_LOADER_PATH], 'exec')
                globals_storage = {}
                globals_storage.update(globals())
                locals_storage = {}
                exec(code, globals_storage, locals_storage)
                globals_storage.update(locals_storage)
                globals_storage[PARAMS] = self.params
                globals_storage[CONFIGS] = self.configs
                globals_storage[TAIL] = copy.deepcopy(self.tail)
                globals_storage[STORAGE] = self.storage
                objects = eval(f"{self.configs[OBJECTS_FUNC]}()",
                            globals_storage, locals_storage)
                super().clear()
                self.update(objects)
                # END: reflect objects
            finally:
                globals().pop(FLEXSRC_CURRENT_ROOT_DIR)
                globals().pop(FLEXSRC_CURRENT_TARGET_NAME)
                os.chdir(cwd)
                # END: chdir

    def load_default_params(path=FSR_FILE):
        if FLEXSRC_CURRENT_ROOT_DIR not in globals():
            # if is invoked from external procedure
            path = Path(path)
            if not path.is_absolute():
                import inspect
                parent = Path(
                           inspect.currentframe().f_back.f_code.co_filename
                         ).parent
                path = parent / path
            config = {DEFAULT_PARAMS: {}}
            config.update(to_object_from_yaml(get_file_contents(path)))
            return config[DEFAULT_PARAMS]
        else:
            return {}


class FlexSrcLeaf(FlexSrc):
    def __init__(self, target, params={}):
        super().__init__(target, params)
        self.body = None

    def clear(self):
        self.body = None

    def update(self, body):
        self.body = body
    
    def get_body(self):
        super().load()
        return self.body
