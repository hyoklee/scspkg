"""
This module is responsbile for building modulefiles in a structured way.
"""
import os
import json
# pylint: disable=W0401,W0614
from jarvis_util import *
# pylint: enable=W0401,W0614
from scspkg.scspkg_manager import ScspkgManager, ModuleType
from abc import ABC, abstractmethod


class Package:
    """
    Package represents a modulefile and the source code for a pacakge.
    """

    def __init__(self, package_name):
        self.scspkg = ScspkgManager.get_instance()
        self.name = package_name
        self.pkg_root = os.path.join(self.scspkg.pkg_dir, package_name)
        self.pkg_src = os.path.join(self.pkg_root, 'src')
        self.module_path = os.path.join(self.scspkg.module_dir, self.name)
        self.module_schema_path = os.path.join(self.pkg_root,
                                               f'{self.name}.yaml')
        self.mod_load_name = f'SCSPKG_{self.name}_LOADED'
        self.sections = {}
        self.reset_config()
        self.load()

    def reset_config(self):
        """
        Create the skeleton configuration.

        :return: self
        """
        self.sections = {}
        self.sections['doc'] = {
            'Name': self.name,
            'Version': 'None',
            'doc': 'None'
        }
        self.sections['deps'] = {}
        self.sections['setenvs'] = {}
        self.sections['prepends'] = {
            'PATH': [os.path.join(self.pkg_root, 'bin'),
                     os.path.join(self.pkg_root, 'sbin')],
            'LD_LIBRARY_PATH': [os.path.join(self.pkg_root, 'lib'),
                                os.path.join(self.pkg_root, 'lib64')],
            'LIBRARY_PATH': [os.path.join(self.pkg_root, 'lib'),
                             os.path.join(self.pkg_root, 'lib64')],
            # 'INCLUDE': [os.path.join(self.pkg_root, 'include')],
            # 'CPATH': [os.path.join(self.pkg_root, 'include')],
            'INCLUDE': [],
            'CPATH': [],
            'CMAKE_PREFIX_PATH': [os.path.join(self.pkg_root, 'cmake')],
            'PYTHONPATH': [os.path.join(self.pkg_root, 'bin'),
                           os.path.join(self.pkg_root, 'lib'),
                           os.path.join(self.pkg_root, 'lib64')],
            'PKG_CONFIG_PATH': [os.path.join(self.pkg_root, 'lib', 'pkgconfig'),
                                os.path.join(self.pkg_root, 'lib64', 'pkgconfig')],
            'CFLAGS': [],
            'LDFLAGS': []
        }
        return self

    def create(self):
        """
        Create the modulefile directories and initial modulefiles.

        :return: self
        """
        os.makedirs(self.pkg_root, exist_ok=True)
        os.makedirs(self.pkg_src, exist_ok=True)
        os.makedirs(f'{self.pkg_root}/include', exist_ok=True)
        os.makedirs(f'{self.pkg_root}/lib', exist_ok=True)
        os.makedirs(f'{self.pkg_root}/lib64', exist_ok=True)
        self.save()
        return self

    def load(self):
        """
        Load the YAML config from the package root
        """
        if os.path.exists(self.module_schema_path):
            self.sections = YamlFile(self.module_schema_path).load()
        return self

    def save(self):
        """
        Save the YAML + modulefiles to the directories.
        """
        YamlFile(self.module_schema_path).save(self.sections)
        if self.scspkg.module_type == ModuleType.TCL:
            self._save_as_tcl()
        elif self.scspkg.module_type == ModuleType.BASH:
            self._save_as_bash()
        return self

    def _save_as_tcl(self):
        """
        Save the TCL representation of the YAML schema

        :return: None
        """
        module = []
        # The module header
        module.append('#%Module1.0')
        # The module doc
        for doc_key, doc_val in self.sections['doc'].items():
            module.append(f'module-whatis \'{doc_key}: {doc_val}\'')
        # The module dependencies
        for dep in self.sections['deps'].keys():
            module.append(f'module load {dep}')
        # The module environment variables
        for env, env_data in self.sections['setenvs'].items():
            module.append(f'setenv {env} {env_data}')
        # The module environment prepends
        for env, values in self.sections['prepends'].items():
            for env_data in values:
                module.append(f'prepend-path {env} {env_data}')
        # Write the lines
        with open(self.module_path, 'w', encoding='utf-8') as fp:
            module = '\n'.join(module)
            fp.write(module)

    def _save_as_bash(self):
        """
        Save the bash representation of the YAML schema

        :return: None
        """
        module = []
        # The module header
        module.append('#!/bin/bash')
        # The module doc
        for doc_key, doc_val in self.sections['doc'].items():
            module.append(f'# \"{doc_key}: {doc_val}\"')
        # The module dependencies
        for dep in self.sections['deps'].keys():
            module.append(f'$(scspkg module load {dep})')
        # The module environment variables
        module.append('$(scspkg module load )')
        # Write the lines
        with open(self.module_path, 'w', encoding='utf-8') as fp:
            module = '\n'.join(module)
            fp.write(module)

    def destroy(self):
        """
        Destroy all data for this package

        :return: self
        """
        Rm(self.pkg_root)
        Rm(self.module_path)
        return self

    def set_env(self, env_name, env_data):
        """
        Set the value of an environment variable.

        :param env_name: the environment variable to set
        :param env_data: the value of the variable
        :return: self
        """
        self.sections['setenvs'][env_name] = env_data
        if env_name in self.sections['prepends']:
            del self.sections['prepends'][env_name]
        return self

    def prepend_env(self, env_name, env_data):
        """
        Prepend data to an environment variable

        :param env_name: The environment variable to prepend to
        :param env_data: A list or string of the data to prepend
        :return: self
        """
        if isinstance(env_data, str):
            env_data = [env_data]
        if env_name not in self.sections['prepends']:
            self.sections['prepends'][env_name] = []
        self.sections['prepends'][env_name] += env_data
        return self

    def append_env(self, env_name, env_data):
        """
        Append data to an environment variable

        :param env_name: The environment variable to prepend to
        :param env_data: A list or string of the data to prepend
        :return: self
        """
        if isinstance(env_data, str):
            env_data = [env_data]
        if env_name not in self.sections['appends']:
            self.sections['appends'][env_name] = []
        env_data += self.sections['appends'][env_name]
        self.sections['appends'][env_name] = env_data
        return self

    def rm_env(self, env_name):
        """
        Remove an environment

        :param env_name: The environment variable to remove
        :return: self
        """
        if env_name in self.sections['setenvs']:
            del self.sections['setenvs'][env_name]
        if env_name in self.sections['prepends']:
            del self.sections['prepends'][env_name]
        return self

    def pop_prepend(self, env_name, env_data):
        """
        Remove one of the prepend paths from this module

        :param env_name: The name of the environment variable in question
        :param env_data: The entry to remove
        :return: self
        """
        if env_name in self.sections['prepends']:
            prepends = self.sections['prepends'][env_name]
            if env_data in prepends:
                prepends.remove(env_data)
            else:
                print(f'{env_data} not in {env_name} prepend variable')
        else:
            print(f'{env_name} is not a prepend variable')
        return self

    def build_profile(self, path=None, rebuild=False):
        """
        Create a snapshot of important currently-loaded environment variables.

        :return: self
        """
        profile = self.scspkg.build_profile(path)
        if rebuild:
            self.reset_config()
            for env_key, env_data in profile.items():
                self.append_env(env_key, env_data)
        return self

    def add_deps(self, deps):
        """
        Add dependencies to the module

        :param deps: A list or string of exact module names
        :return: self
        """
        if isinstance(deps, str):
            deps = [deps]
        for dep in deps:
            self.sections['deps'][dep] = True
        return self

    def pop_deps(self, deps):
        """
        Remove dependencies in the module

        :param deps: A list or string of exact module names
        :return: self
        """
        if isinstance(deps, str):
            deps = [deps]
        for dep in deps:
            if dep in self.sections['deps']:
                del self.sections['deps'][dep]
        self.save()
        return self

    def ls_deps(self):
        """
        Print all dependencies of the module
        """
        for dep in self.sections['deps'].keys():
            print(dep)

    def get_module_schema(self):
        """
        Load the contents of the YAML module schema
        """
        if os.path.exists(self.module_schema_path):
            return json.dumps(self.sections, indent=4)
        else:
            print(f'Error: Package {self.name} does not exist')
            sys.exit(1)

    def get_modulefile(self):
        """
        Load the text of the modulefile

        :return: String
        """
        if os.path.exists(self.module_path):
            with open(self.module_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            print(f'Error: Package {self.name} does not exist')
            sys.exit(1)

    def get_script_loader(self):
        if self.scspkg.module_type == ModuleType.TCL:
            print('Use "module load instead" of "scspkg module load"')
            return
        elif self.scspkg.module_type == ModuleType.BASH:
            return BashLoader(self)
        else:
            print(f'Error: Unknown module type {self.scspkg.module_type}')

    def module_load(self):
        """
        Create the script to load this module

        :return: None
        """
        scripter = self.get_script_loader()
        if not scripter:
            return
        return scripter.module_load()
        
    def module_unload(self):
        """
        Create the script to unload this module

        :return: None
        """
        scripter = self.get_script_loader()
        if not scripter:
            return
        return scripter.module_unload()


class ScriptLoader(ABC):
    """
    Abstract class to load scripts
    """

    def __init__(self, pkg):
        self.pkg = pkg
        self.scspkg = ScspkgManager.get_instance()
        self.name = self.pkg.name
        self.mod_load_name = self.pkg.mod_load_name
        self.sections = self.pkg.sections

    def is_loaded(self):
        """
        Check if this module is loaded in the current bash session

        :return: True or False
        """
        if os.environ.get(self.mod_load_name):
            return True
        return False
    
    def module_load(self):
        """
        Create the script to load this module in bash

        :return: None
        """
        # Verify that the module is not loaded
        if self.is_loaded():
            print(f'Module {self.name} is already loaded')
            exit(1)
        envs = []

        # Process setenvs
        for env, env_data in self.sections['setenvs'].items():
            envs.append(self.set_env(env, env_data))

        # Process prepends
        for env, values in self.sections['prepends'].items():
            if values:
                envs.append(self.prepend_env(env, values))
        
        # Mark this module as loaded
        envs.append(self.set_env(self.mod_load_name, '1'))
        return '\n'.join(envs)

    def module_unload(self):
        """
        Create the script to unload this module in bash

        :return: None
        """
        # Verify that the module is loaded
        if not self.is_loaded():
            print(f'Module {self.name} is not loaded')
            exit(1)
        envs = []

        # Process setenvs
        for env in self.sections['setenvs'].keys():
            envs.append(self.unset_env(env))

        # Process prepends
        for env, values in self.sections['prepends'].items():
            if values:
                path_str = ':'.join(values)
                if env in os.environ:
                    os.environ[env] = os.environ[env].replace(path_str, '').strip(':')
                    envs.append(self.set_env(env, os.environ[env]))

        # Mark this module as unloaded
        self.unset_env(self.mod_load_name)
        return '\n'.join(envs)

    @abstractmethod
    def set_env(self, env_name, env_data):
        """
        Set the value of an environment variable.

        :param env_name: the environment variable to set
        :param env_data: the value of the variable
        :return: self
        """
        pass

    @abstractmethod
    def prepend_env(self, env_name, env_data):
        """
        Prepend data to an environment variable

        :param env_name: The environment variable to prepend to
        :param env_data: A list or string of the data to prepend
        :return: self
        """
        pass

    @abstractmethod
    def unset_env(self, env_name):
        """
        Remove an environment

        :param env_name: The environment variable to remove
        :return: self
        """
        pass
    

class BashLoader(ScriptLoader):
    """
    Class to load bash scripts
    """
    def set_env(self, env_name, env_data):
        """
        Set the value of an environment variable in bash
        :param env_name: the environment variable to set
        :param env_data: the value of the variable
        :return: None
        """
        return f'export {env_name}={env_data}'
    
    def prepend_env(self, env_name, values):
        """
        Prepend data to an environment variable in bash
        :param env_name: The environment variable to prepend to
        :param values: A list of the data to prepend
        :return: None
        """
        path_str = ':'.join(values)
        env_val = os.environ[env_name]
        if env_name in os.environ:
            return f'export {env_name}={path_str}:{env_val}'
        else:
            return f'export {env_name}={path_str}'
    
    def unset_env(self, env_name):
        """
        Unset the value of an environment variable in bash
        :param env_name: the environment variable to unset
        :return: None
        """
        return f'unset {env_name}'