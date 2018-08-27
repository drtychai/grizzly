# coding=utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import shutil
import tempfile
import time

__author__ = "Tyson Smith"
__credits__ = ["Tyson Smith"]

class InputFile(object):
    CACHE_LIMIT = 0x100000  # 1MB

    def __init__(self, file_name):
        assert file_name is not None
        self.extension = None
        self.file_name = file_name
        self._fp = None

        if not os.path.isfile(file_name):
            raise IOError("File does %r does not exist" % self.file_name)

        # TODO: add kwarg to set self.extension?
        if "." in self.file_name:
            self.extension = os.path.splitext(self.file_name)[-1].lstrip(".")


    def _cache_data(self):
        self._fp = tempfile.SpooledTemporaryFile(max_size=self.CACHE_LIMIT)
        with open(self.file_name, "rb") as src_fp:
            shutil.copyfileobj(src_fp, self._fp, 0x10000)  # 64KB


    def close(self):
        if self._fp is not None:
            self._fp.close()
        self._fp = None


    def get_data(self):
        """
        get_data()
        Provide the raw input file data to the caller.

        returns input file data from file.read()
        """

        if self._fp is None:
            self._cache_data()
        self._fp.seek(0)
        # TODO: add size limit
        return self._fp.read()


    def get_fp(self):
        if self._fp is None:
            self._cache_data()
        self._fp.seek(0)
        return self._fp


class TestCase(object):
    def __init__(self, landing_page, redirect_page, adapter_name, input_fname=None):
        self.adapter_name = adapter_name
        self.landing_page = landing_page
        self.redirect_page = redirect_page
        self.input_fname = input_fname  # file that was used to create the test case
        self._env_vars = dict()  # environment variables
        self._files = {  # contains TestFile(s) that make up a test case
            "meta": list(),  # environment files such as prefs.js, etc...
            "optional": list(),
            "required": list()}
        self._started = None  # approximate time execution began


    def add_meta(self, meta_file):
        assert isinstance(meta_file, TestFile), "only accepts TestFiles"
        self._files["meta"].append(meta_file)


    def add_environ_var(self, var_name, value):
        self._env_vars[var_name] = value


    def add_file(self, test_file, required=True):
        assert isinstance(test_file, TestFile), "only accepts TestFiles"
        key = "required" if required else "optional"
        self._files[key].append(test_file)


    def add_from_data(self, data, file_name, encoding="UTF-8", required=True):
        self.add_file(
            TestFile.from_data(data=data, file_name=file_name, encoding=encoding),
            required=required)


    def add_from_file(self, input_file, file_name, required=True):
        self.add_file(
            TestFile.from_file(input_file=input_file, file_name=file_name),
            required=required)


    def dump(self, log_dir, include_details=False):
        """
        dump(log_dir)
        Write all the test case data to the filesystem.
        This includes:
        - the generated test case
        - details of input file used
        All data will be located in log_dir.

        returns None
        """

        # save test files to log_dir
        for test_file in self._files["required"] + self._files["optional"]:
            test_file.dump(log_dir)

        # save test case, input file, file information, environment info
        if include_details:
            # TODO: make this metadata.json
            with open(os.path.join(log_dir, "test_info.txt"), "w") as out_fp:
                out_fp.write("[Grizzly test case details]\n")
                out_fp.write("Adapter:    %s\n" % self.adapter_name)
                out_fp.write("Landing Page:      %s\n" % self.landing_page)
                if self.input_fname is not None:
                    out_fp.write("Input File:        %s\n" % os.path.basename(self.input_fname))

            if self._env_vars:
                # TODO: make this metadata.json
                with open(os.path.join(log_dir, "env_vars.txt"), "w") as out_fp:
                    for env_var, env_val in self._env_vars.items():
                        out_fp.write("%s=%s\n" % (env_var, env_val))

            # save meta files
            for meta_file in self._files["meta"]:
                meta_file.dump(log_dir)


    def set_started(self):
        self._started = time.time()


    def cleanup(self):
        # close all the test files
        for file_group in self._files.values():
            for test_file in file_group:
                test_file.close()


    def get_optional(self):
        return [x.file_name for x in self._files["optional"]]


    def env_vars(self):
        return ["=".join(pair) for pair in self._env_vars.items()]


class TestFile(object):
    CACHE_LIMIT = 0x40000  # data cache limit per file: 256KB
    XFER_BUF = 0x10000  # transfer buffer size: 64KB

    def __init__(self, file_name):
        self._fp = tempfile.SpooledTemporaryFile(max_size=self.CACHE_LIMIT, mode="r+b", prefix='grz_tf_')
        self.file_name = os.path.normpath(file_name)  # name including path relative to wwwroot

        # XXX: This is a naive fix for a larger path issue
        if "\\" in self.file_name:
            self.file_name.replace("\\", "/")
        self.file_name = self.file_name.lstrip("/")


    def clone(self):
        cloned = TestFile(self.file_name)
        self._fp.seek(0)
        shutil.copyfileobj(self._fp, cloned._fp, self.XFER_BUF)  # pylint: disable=protected-access
        return cloned


    def close(self):
        self._fp.close()


    def dump(self, path):
        target_path = os.path.join(path, os.path.dirname(self.file_name))
        if not os.path.isdir(target_path):
            os.makedirs(target_path)
        self._fp.seek(0)
        with open(os.path.join(path, self.file_name), "wb") as dst_fp:
            shutil.copyfileobj(self._fp, dst_fp, self.XFER_BUF)


    @classmethod
    def from_data(cls, data, file_name, encoding="UTF-8"):
        t_file = cls(file_name=file_name)
        if data:
            if isinstance(data, bytes) or not encoding:
                t_file.write(data)
            else:
                t_file.write(data.encode(encoding))
        return t_file


    @classmethod
    def from_file(cls, input_file, file_name):
        t_file = cls(file_name=file_name)
        with open(input_file, "rb") as src_fp:
            shutil.copyfileobj(src_fp, t_file._fp, cls.XFER_BUF)  # pylint: disable=protected-access
        return t_file


    def write(self, data):
        self._fp.write(data)
