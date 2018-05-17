# coding=utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import zipfile

import pytest

from grizzly.reduce.args import ReducerArgs, ReducerFuzzManagerIDArgs
from grizzly.reduce import reduce, crash, bucket
from grizzly import reporter
from .test_reduce import job  # noqa pylint: disable=unused-import


def test_parse_args(capsys, tmpdir):
    "test that grizzly.reduce args are accepted and validated"
    exe = tmpdir.join("binary")
    inp = tmpdir.join("input")

    # missing arg tests
    with pytest.raises(SystemExit):
        ReducerArgs().parse_args([])
    _, err = capsys.readouterr()
    with pytest.raises(SystemExit):
        ReducerArgs().parse_args([exe.strpath])
    _, err = capsys.readouterr()

    # invalid binary tests
    with pytest.raises(SystemExit):
        ReducerArgs().parse_args([exe.strpath, inp.strpath])
    _, err = capsys.readouterr()
    assert "error: file not found: '%s'" % (exe.strpath,) in err
    exe.ensure(dir=True)
    with pytest.raises(SystemExit):
        ReducerArgs().parse_args([exe.strpath, inp.strpath])
    _, err = capsys.readouterr()
    assert "error: file not found: '%s'" % (exe.strpath,) in err
    exe.remove()
    exe.ensure()

    # invalid input tests
    with pytest.raises(SystemExit):
        ReducerArgs().parse_args([exe.strpath, inp.strpath])
    _, err = capsys.readouterr()
    assert "error: '%s' does not exist" % (inp.strpath,) in err
    inp.ensure()
    with pytest.raises(SystemExit):
        ReducerArgs().parse_args([exe.strpath, inp.strpath])
    _, err = capsys.readouterr()
    assert "error: Testcase should be a folder or zip" in err
    inp.remove()
    with pytest.raises(SystemExit):
        ReducerFuzzManagerIDArgs().parse_args([exe.strpath, inp.strpath])
    _, err = capsys.readouterr()
    assert "invalid int value" in err

    # valid binary & inputs
    zipf = tmpdir.ensure("input.zip")
    ReducerArgs().parse_args([exe.strpath, zipf.strpath])
    zipf.remove()
    inp.ensure(dir=True).ensure("test_info.txt")
    ReducerArgs().parse_args([exe.strpath, inp.strpath])
    ReducerFuzzManagerIDArgs().parse_args([exe.strpath, '123'])

    # sig/environ tests
    fname = tmpdir.join("file.txt")
    for arg in ("--sig", "--environ"):
        with pytest.raises(SystemExit):
            ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, fname.strpath])
        _, err = capsys.readouterr()
        assert "error: file not found: '%s'" % (fname.strpath,) in err
        fname.ensure(dir=True)
        with pytest.raises(SystemExit):
            ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, fname.strpath])
        _, err = capsys.readouterr()
        assert "error: file not found: '%s'" % (fname.strpath,) in err
        fname.remove()
        fname.ensure()
        ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, fname.strpath])
        fname.remove()

    # repeat/min-crashes tests
    for arg in ("--repeat", "--min-crashes"):
        with pytest.raises(SystemExit):
            ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, "abc"])
        with pytest.raises(SystemExit):
            ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, "-1"])
        _, err = capsys.readouterr()
        assert "'%s' value must be positive" % (arg,) in err
        with pytest.raises(SystemExit):
            ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, "0"])
        _, err = capsys.readouterr()
        assert "'%s' value must be positive" % (arg,) in err
        ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, "1"])
        ReducerArgs().parse_args([exe.strpath, inp.strpath, arg, "10"])


def test_main(job, monkeypatch, tmpdir):  # noqa pylint: disable=redefined-outer-name
    "simple test that main functions"
    # uses the job fixture from test_reduce which reduces testcases to the string "required\n"
    monkeypatch.setattr(reduce, "ReductionJob", lambda *a, **kw: job)

    exe = tmpdir.ensure("binary")
    inp = tmpdir.ensure("input", dir=True)
    inp.ensure("test_info.txt").write("landing page: test.html")
    inp.ensure("test.html").write("fluff\nrequired\n")
    args = ReducerArgs().parse_args([exe.strpath, inp.strpath])
    assert reduce.main(args) == 0


def test_bucket_main(job, monkeypatch, tmpdir):  # noqa pylint: disable=redefined-outer-name
    "bucket.main iterates using crash.main"
    main_called = [0]

    class FakeCollector(object):
        serverProtocol = 'https'
        serverHost = 'mozilla.org'
        serverPort = 8000

        def get(self, _url, **kwds):
            class response(object):
                @staticmethod
                def json():
                    if "crashes" in _url:
                        return {
                            "results": [
                                {"testcase": None, "id": 123},
                                {"testcase": True, "id": 456},
                            ],
                            "next": None,
                            "count": 2,
                        }
                    else:
                        return {
                            "signature": '{"symptoms": []}',
                        }
            return response

    def crash_main(args):
        assert args.input == 456
        main_called[0] += 1
        return 0

    monkeypatch.setattr(bucket, "Collector", FakeCollector)
    monkeypatch.setattr(bucket, "reduce_crash", crash_main)

    exe = tmpdir.ensure("binary")
    args = ReducerFuzzManagerIDArgs().parse_args([exe.strpath, '789'])
    assert bucket.main(args) == 0
    assert main_called[0] == 1


def test_crash_main(job, monkeypatch, tmpdir):  # noqa pylint: disable=redefined-outer-name
    "crash.main --fuzzmanager updates quality"
    # expect Collector.patch to be called with these qualities
    expect_patch = [reporter.FuzzManagerReporter.QUAL_REPRODUCIBLE,
                    reporter.FuzzManagerReporter.QUAL_REDUCED_ORIGINAL]
    submitted = [False]

    class ReporterNoSubmit(reporter.FuzzManagerReporter):

        def _submit(self):
            # check that the crash was already marked reproducible, but not yet marked reduced
            assert expect_patch == [reporter.FuzzManagerReporter.QUAL_REDUCED_ORIGINAL]
            submitted[0] = True

    class FakeCollector(object):
        serverProtocol = 'https'
        serverHost = 'mozilla.org'
        serverPort = 8000

        def get(self, _url):
            class response(object):
                class headers(object):
                    @staticmethod
                    def get(value, default):
                        assert value.lower() == 'content-disposition'
                        return 'attachment; filename="test.zip"'
                content = inp.join("test.zip").read('rb')
            return response

        def patch(self, _url, data):
            assert set(data.keys()) == {"testcase_quality"}
            assert expect_patch
            assert data["testcase_quality"] == expect_patch.pop(0)

    # uses the job fixture from test_reduce which reduces testcases to the string "required\n"
    monkeypatch.setattr(reduce, "ReductionJob", lambda *a, **kw: job)
    monkeypatch.setattr(reporter, "Collector", FakeCollector)
    monkeypatch.setattr(reporter, "FuzzManagerReporter", ReporterNoSubmit)
    monkeypatch.setattr(crash, "Collector", FakeCollector)

    exe = tmpdir.ensure("binary")
    tmpdir.join("binary.fuzzmanagerconf").write(
        "[Main]\n"
        "platform = x86-64\n"
        "product = mozilla-central\n"
        "os = linux\n"
    )
    inp = tmpdir.ensure("input", dir=True)
    inp.ensure("test_info.txt").write("landing page: test.html")
    inp.ensure("test.html").write("fluff\nrequired\n")
    with zipfile.ZipFile(inp.join("test.zip").strpath, "w") as zip_fp:
        zip_fp.write(inp.join("test_info.txt").strpath, "test_info.txt")
        zip_fp.write(inp.join("test.html").strpath, "test.html")
    args = ReducerFuzzManagerIDArgs().parse_args([exe.strpath, '1234', '--fuzzmanager'])
    assert crash.main(args) == 0
    assert not expect_patch
    assert submitted[0]