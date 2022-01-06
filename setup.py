#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import pathlib

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as build_ext

CFLAGS = ['-O2']

ROOT = pathlib.Path(__file__).parent

CYTHON_DEPENDENCY = 'Cython(>=0.29.24,<0.30.0)'


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    path = os.path.join(package, "__init__.py")
    init_py = open(path, "r", encoding="utf8").read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


def get_long_description():
    """
    Return the README.
    """
    return open("README.md", "r", encoding="utf8").read()


def get_packages(package):
    """
    Return root package and all sub-packages.
    """
    return [
        dirpath
        for dirpath, dirnames, filenames in os.walk(package)
        if os.path.exists(os.path.join(dirpath, "__init__.py"))
    ]


env_marker_cpython = (
    "sys_platform != 'win32'"
    " and (sys_platform != 'cygwin'"
    " and platform_python_implementation != 'PyPy')"
)

env_marker_win = "sys_platform == 'win32'"

minimal_requirements = [
    "asgiref>=3.4.0",
    "click>=7.0",
    "h11>=0.8",
    "Cython(>=0.29.24,<0.30.0)",
]


extra_requirements = [
    "websockets>=10.0",
    "uvloop>=0.14.0,!=0.15.0,!=0.15.1; " + env_marker_cpython,
    "colorama>=0.4;" + env_marker_win,
    "watchgod>=0.6",
    "python-dotenv>=0.13",
    "PyYAML>=5.1",
]


setup_requires = []

if (not (ROOT / 'esg' / 'protocols' / 'http' / 'parser.c').exists() or
        '--cython-always' in sys.argv):
    # No Cython output, require Cython to build.
    setup_requires.append(CYTHON_DEPENDENCY)


class httptools_build_ext(build_ext):
    user_options = build_ext.user_options + [
        ('cython-always', None,
            'run cythonize() even if .c files are present'),
        ('cython-annotate', None,
            'Produce a colorized HTML version of the Cython source.'),
        ('cython-directives=', None,
            'Cythion compiler directives'),
        ('use-system-llhttp', None,
            'Use the system provided llhttp, instead of the bundled one'),
        ('use-system-http-parser', None,
            'Use the system provided http-parser, instead of the bundled one'),
    ]

    boolean_options = build_ext.boolean_options + [
        'cython-always',
        'cython-annotate',
        'use-system-llhttp',
        'use-system-http-parser',
    ]

    def initialize_options(self):
        # initialize_options() may be called multiple times on the
        # same command object, so make sure not to override previously
        # set options.
        if getattr(self, '_initialized', False):
            return

        super().initialize_options()
        self.use_system_llhttp = False
        self.use_system_http_parser = False
        self.cython_always = True
        self.cython_annotate = None
        self.cython_directives = None

    def finalize_options(self):
        # finalize_options() may be called multiple times on the
        # same command object, so make sure not to override previously
        # set options.
        if getattr(self, '_initialized', False):
            return

        need_cythonize = self.cython_always
        cfiles = {}

        for extension in self.distribution.ext_modules:
            for i, sfile in enumerate(extension.sources):
                if sfile.endswith('.pyx'):
                    prefix, ext = os.path.splitext(sfile)
                    cfile = prefix + '.c'

                    if os.path.exists(cfile) and not self.cython_always:
                        extension.sources[i] = cfile
                    else:
                        if os.path.exists(cfile):
                            cfiles[cfile] = os.path.getmtime(cfile)
                        else:
                            cfiles[cfile] = 0
                        need_cythonize = True

        if need_cythonize:
            try:
                import Cython
            except ImportError:
                raise RuntimeError(
                    'please install Cython to compile httptools from source')

            if Cython.__version__ < '0.29':
                raise RuntimeError(
                    'httptools requires Cython version 0.29 or greater')

            from Cython.Build import cythonize

            directives = {}
            if self.cython_directives:
                for directive in self.cython_directives.split(','):
                    k, _, v = directive.partition('=')
                    if v.lower() == 'false':
                        v = False
                    if v.lower() == 'true':
                        v = True

                    directives[k] = v

            self.distribution.ext_modules[:] = cythonize(
                self.distribution.ext_modules,
                compiler_directives=directives,
                annotate=self.cython_annotate)

        super().finalize_options()

        self._initialized = True

    def build_extensions(self):
        mod_parser, mod_flow_control = self.distribution.ext_modules
        # if self.use_system_llhttp:
        #     mod_parser.libraries.append('llhttp')
        #     mod_parser.libraries.append('http_parser')
        #
        #     if sys.platform == 'darwin' and \
        #             os.path.exists('/opt/local/include'):
        #         # Support macports on Mac OS X.
        #         mod_parser.include_dirs.append('/opt/local/include')
        # else:
        mod_parser.include_dirs.append(
            str(ROOT / 'vendor' / 'llhttp' / 'include'))
        mod_parser.include_dirs.append(
            str(ROOT / 'vendor' / 'llhttp' / 'src'))
        mod_parser.sources.append('vendor/llhttp/src/api.c')
        mod_parser.sources.append('vendor/llhttp/src/http.c')
        mod_parser.sources.append('vendor/llhttp/src/llhttp.c')
        mod_parser.include_dirs.append(
            str(ROOT / 'vendor' / 'http-parser'))
        mod_parser.sources.append(
            'vendor/http-parser/http_parser.c')

        super().build_extensions()


setup(
    name="esg",
    version=get_version("esg"),
    url="https://github.com/mtag-dev/esg",
    license="BSD",
    description="Enhanced Service Gateway",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Stanislav Dubrovskyi",
    author_email="s.dubrovskyi@cleverdec.com",
    packages=get_packages("esg"),
    install_requires=minimal_requirements,
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    entry_points="""
    [console_scripts]
    esg=esg.main:main
    """,
    project_urls={
        "Source": "https://github.com/mtag-dev/esg",
        "Changelog": "https://github.com/mtag-dev/esg/blob/master/CHANGELOG.md",
    },

    cmdclass={
        'build_ext': httptools_build_ext,
    },
    ext_modules=[
        Extension(
            "esg.protocols.http.protocol",
            sources=[
                "esg/protocols/http/protocol.pyx",
            ],
            extra_compile_args=CFLAGS,
        ),
        Extension(
            "esg.protocols.http.flow_control",
            sources=[
                "esg/protocols/http/flow_control.pyx",
            ],
            extra_compile_args=CFLAGS,
        ),
    ],
    test_suite='tests.suite',
    setup_requires=setup_requires,
    extras_require={
        "standard": extra_requirements,
        "test": [
            CYTHON_DEPENDENCY
        ]
    }
)
