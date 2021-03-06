# coding=utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from sys import exit as sysexit

from .args import ReducerArgs
from .reduce import ReductionJob


sysexit(ReductionJob.main(ReducerArgs().parse_args()))
