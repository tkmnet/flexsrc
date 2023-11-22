import os
import sys
import tempfile
from typing import Any
from pathlib import Path
import json
import yaml
import xxhash

FLEXSRC = 'FlexSrc'
FSR_FILE = '__fsr__.yaml'
FSR_EXT = '.fsr.yaml'
CONFIG_FILE = 'flexsrc.yaml'
REPO_CACHE_DIR = 'repo_cache_dir'
DATA_CACHE_DIR = 'data_cache_dir'
CACHE_PATH = 'cache_path'
OBJECT_LOADER = 'object_loader'
OBJECT_LOADER_PATH = 'object_loader_path'
DEFAULT_OBJECT_LOADER = '__fsr__.py'
LOCAL = 'local'
IS_LOCAL = 'is_local'
PATH = 'path'
FLEXSRC_CURRENT_ROOT_DIR = 'flexsrc_current_root_dir'
FLEXSRC_CURRENT_TARGET_NAME = 'flexsrc_current_target_name'
WORK_DIR = 'work_dir'
PARAMS = 'params'
CONFIGS = 'configs'
DEFAULT_PARAMS = 'default_params'
OBJECTS_FUNC = 'objects_func'
DEFAULT_OBJECTS_FUNC = 'objects'
INFO = 'info'
DATA = 'data'
REPO = 'repo'
ID = 'id'


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
        obj = super().__getitem__(__key)
        if isinstance(obj, FlexSrcLeaf):
            return obj.get_body()
        elif isinstance(obj, FlexSrc):
            return obj
        elif isinstance(obj, dict):
            return FSIndirectObject(obj)
        return obj


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


class FlexSrc(FSIndirectObject):
    def __init__(self, target, params={}):
        pre_load = True
        root_dir = None
        self.target = target
        self.forced_objects_func = None
        self.target_name = target
        self.fsr_id = ''
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
        self.config_loaded = False
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
        if pre_load:
            self.load()

    def __str__(self) -> str:
        self.load()
        return f"{self.__class__.__name__}({self.target_name}{repr(self.params)}): {super().__repr__()}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.target_name}{repr(self.params)})"

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

    def __getitem__(self, __key: Any) -> Any:
        self.load()
        return super().__getitem__(__key)

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

    def try_load_fsr_yaml(self):
        fsr_yaml = '{}'
        if os.path.isdir(Path(self.root_dir) / self.target)\
           and os.path.isfile(Path(self.root_dir) / self.target / FSR_FILE):
            fsr_yaml = get_file_contents(
                         Path(self.root_dir) / self.target / FSR_FILE)
            self.configs[PATH] = Path(self.root_dir) / self.target
        elif os.path.isfile(Path(self.root_dir) / (self.target + FSR_EXT)):
            fsr_yaml = get_file_contents(self.target + FSR_EXT)
            self.configs[PATH] = Path(self.root_dir)
        self.configs.update(to_object_from_yaml(fsr_yaml))
        if ID in self.configs:
            self.fsr_id = self.configs[ID]
        else:
            self.fsr_id = xxhash.xxh32(fsr_yaml).hexdigest()
        self.configs[CACHE_PATH] = Path(LOCAL) / f"{self.target}-{self.fsr_id}"
        self.configs[IS_LOCAL] = True

    def arrenge_configs(self):
        c = self.configs
        c[WORK_DIR] = c[DATA_CACHE_DIR] / c[CACHE_PATH]
        c[OBJECT_LOADER_PATH] = c[PATH] / c[OBJECT_LOADER]
        if self.forced_objects_func is not None:
            c[OBJECTS_FUNC] = self.forced_objects_func

    def load_config(self):
        if not self.config_loaded:
            self.config_loaded = True
            self.try_load_configs()
            self.prepare_cache_dir()
            self.try_load_fsr_yaml()
            self.arrenge_configs()

    def load_params(self, storage):
        self.load_config()
        storage.update(self.configs[DEFAULT_PARAMS])

    def clear(self) -> None:
        self.loaded_params_str = None
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
            os.makedirs(self.configs[WORK_DIR], exist_ok=True)
            os.chdir(self.configs[WORK_DIR])
            # BEGIN: arrange globals
            globals()[FLEXSRC_CURRENT_ROOT_DIR] = self.configs[PATH]
            globals()[FLEXSRC_CURRENT_TARGET_NAME] = self.target_name
            # BEGIN: reflect objects
            # print("### EVAL ### " + self.target_name)
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
            objects = eval(f"{self.configs[OBJECTS_FUNC]}()",
                           globals_storage, locals_storage)
            super().clear()
            self.update(objects)
            # END: reflect objects
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
            config.update(get_yamlfile_contents(path))
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