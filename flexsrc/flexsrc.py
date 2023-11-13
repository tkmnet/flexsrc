import os
import sys
import tempfile
from typing import Any
import yaml
from pathlib import Path

FSR_FILE = 'fsr.yaml'
FSR_EXT = f".{FSR_FILE}"
CONFIG_FILE = 'flexsrc.yaml'
REPO_CACHE_DIR = 'repo_cache_dir'
DATA_CACHE_DIR = 'data_cache_dir'
CACHE_PATH = 'cache_path'
OBJECT_LOADER = 'object_loader'
OBJECT_LOADER_PATH = 'object_loader_path'
DEFAULT_OBJECT_LOADER = 'fsr.py'
IS_LOCAL = 'is_local'
PATH = 'path'
FLEXSRC_CURRENT_ROOT_DIR = 'flexsrc_current_root_dir'
FLEXSRC_CURRENT_TARGET_NAME = 'flexsrc_current_target_name'
WORK_DIR = 'work_dir'
PARAMS = 'params'
DEFAULT_PARAMS = 'default_params'
OBJECTS_FUNC = 'objects_func'
DEFAULT_OBJECTS_FUNC = 'objects'
INFO = 'info'


def get_file_contents(path):
    res = None
    if os.path.isfile(path):
        with open(path, 'r') as file:
            res = file.read()
    return res


def get_yamlfile_contents(path):
    contents = get_file_contents(path)
    if contents is not None:
        try:
            contents = yaml.safe_load(contents)
            if isinstance(contents, dict):
                return contents
        except Exception as e:
            print(e, file=sys.stderr)
    return {}


class FSIndirectObject(dict):
    def __init__(self, obj):
        self.update(obj)

    def __exit__(self, *args):
        self.clear()

    def __getitem__(self, __key: Any) -> Any:
        obj = super().__getitem__(__key)
        if isinstance(obj, FlexSrc):
            return obj
        elif isinstance(obj, dict):
            return FSIndirectObject(obj)
        return obj


class FSParams(dict):
    def __init__(self, holder, obj):
        self.holder = holder
        self.initialized = False
        self.loaded_default_repr = super().__repr__()
        if len(obj) > 0:
            self.initialize()
        self.update(obj)

    def __str__(self) -> str:
        self.initialize()
        return super().__repr__() if self.__len__() > 0 else '{}'

    def __repr__(self) -> str:
        repr = super().__repr__()
        return repr if self.__len__() > 0\
                       and self.loaded_default_repr != repr else ''

    def __call__(self):
        print(str(self))
        return self

    def initialize(self):
        if not self.initialized:
            self.initialized = True
            self.holder.load_params(self)
            self.loaded_default_repr = super().__repr__()


class FlexSrc(FSIndirectObject):
    def __init__(self, target, params={}):
        pre_load = True
        root_dir = None
        self.target = target
        self.forced_objects_func = None
        self.target_name = target
        if callable(target):
            self.target = '.'
            self.forced_objects_func = target.__name__
            self.target_name = f"{globals()[FLEXSRC_CURRENT_TARGET_NAME]}\
                                 .{target.__name__}"
        if root_dir is None:
            if FLEXSRC_CURRENT_ROOT_DIR in globals():
                root_dir = globals()[FLEXSRC_CURRENT_ROOT_DIR]
                pre_load = False
            else:
                root_dir = os.getcwd()
        self.root_dir = root_dir
        self.config_loaded = False
        self.loaded_params_str = None
        self.config = {
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
        return f"{self.__class__.__name__}\
                 ({self.target_name}{repr(self.params)})\
                 : {super().__repr__()}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}\
                 ({self.target_name}{repr(self.params)})"

    def __call__(self):
        print(str(self))
        return self

    def __getitem__(self, __key: Any) -> Any:
        self.load()
        return super().__getitem__(__key)

    def try_load_configs(self):
        self.config.update(
          get_yamlfile_contents(
            Path(os.path.expanduser('~')) / ('.' + CONFIG_FILE)))
        self.config.update(
          get_yamlfile_contents(
            Path(os.path.expanduser('~')) / CONFIG_FILE))
        self.config.update(get_yamlfile_contents('.' + CONFIG_FILE))
        self.config.update(get_yamlfile_contents(CONFIG_FILE))

    def prepare_cache_dir(self):
        if self.config[REPO_CACHE_DIR] is None:
            with tempfile.TemporaryDirectory() as d:
                self.config[REPO_CACHE_DIR] =\
                  Path(d).parent / self.__class__.__name__ / 'repo'
        if self.config[DATA_CACHE_DIR] is None:
            with tempfile.TemporaryDirectory() as d:
                self.config[DATA_CACHE_DIR] =\
                  Path(d).parent / self.__class__.__name__ / 'data'
        os.makedirs(self.config[REPO_CACHE_DIR], exist_ok=True)
        os.makedirs(self.config[DATA_CACHE_DIR], exist_ok=True)

    def try_load_fsr_yaml(self):
        if os.path.isdir(Path(self.root_dir) / self.target)\
           and os.path.isfile(Path(self.root_dir) / self.target / FSR_FILE):
            self.config.update(
              get_yamlfile_contents(
                Path(self.root_dir) / self.target / FSR_FILE))
            self.config[PATH] = Path(self.root_dir) / self.target
        elif os.path.isfile(Path(self.root_dir) / (self.target + FSR_EXT)):
            self.config.update(get_yamlfile_contents(self.target + FSR_EXT))
            self.config[PATH] = Path(self.root_dir)
        self.config[CACHE_PATH] = Path('local') / self.target
        self.config[IS_LOCAL] = True

    def arrenge_configs(self):
        c = self.config
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
        storage.update(self.config[DEFAULT_PARAMS])

    def info(self):
        self.load_config()
        return self.config[INFO]

    def load(self):
        params_str = str(self.params)
        if self.loaded_params_str != params_str:
            self.loaded_params_str = params_str
            self.load_config()
            # BEGIN: chdir
            cwd = os.getcwd()
            os.makedirs(self.config[WORK_DIR], exist_ok=True)
            os.chdir(self.config[WORK_DIR])
            # BEGIN: arrange globals
            globals()[FLEXSRC_CURRENT_ROOT_DIR] = self.config[PATH]
            globals()[FLEXSRC_CURRENT_TARGET_NAME] = self.target_name
            # BEGIN: reflect objects
            # print("### EVAL ### " + self.target_name)
            sys.path.append(self.config[PATH])
            code = compile(
                     get_file_contents(
                       self.config[OBJECT_LOADER_PATH]),
                     self.config[OBJECT_LOADER_PATH], 'exec')
            globals_storage = {}
            globals_storage.update(globals())
            locals_storage = {}
            exec(code, globals_storage, locals_storage)
            globals_storage.update(locals_storage)
            globals_storage[PARAMS] = self.params
            objects = eval(f"{self.config[OBJECTS_FUNC]}()",
                           globals_storage, locals_storage)
            self.clear()
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
