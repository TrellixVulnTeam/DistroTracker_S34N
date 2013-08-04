# -*- coding: utf-8 -*-

# Copyright 2013 The Debian Package Tracking System Developers
# See the COPYRIGHT file at the top-level directory of this distribution and
# at http://deb.li/ptsauthors
#
# This file is part of the Package Tracking System. It is subject to the
# license terms in the LICENSE file found in the top-level directory of
# this distribution and at http://deb.li/ptslicense. No part of the Package
# Tracking System, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE file.
from pts.core.models import Architecture
from pts.core.models import ContributorEmail
from pts.core.models import ContributorName
from pts.core.models import SourcePackage
from pts.core.models import SourcePackageName
from pts.core.models import BinaryPackageName

import shutil
import tempfile
import contextlib


@contextlib.contextmanager
def make_temp_directory(suffix=''):
    """
    Helper context manager which creates a temporary directory on enter and
    cleans it up on exit.
    """
    temp_dir_name = tempfile.mkdtemp(suffix=suffix)
    try:
        yield temp_dir_name
    finally:
        shutil.rmtree(temp_dir_name)


def create_source_package(arguments):
    """
    Creates and returns a new :class:`SourcePackage <pts.core.models.SourcePackage>`
    instance based on the parameters given in the arguments.

    It takes care to automatically create any missing maintainers, package
    names, etc.
    """
    kwargs = {}
    if 'maintainer' in arguments:
        maintainer = arguments['maintainer']
        maintainer_email = ContributorEmail.objects.get_or_create(
            email=maintainer['email'])[0]
        kwargs['maintainer'] = ContributorName.objects.get_or_create(
            contributor_email=maintainer_email,
            name=maintainer.get('name', ''))[0]
    if 'name' in arguments:
        name = arguments['name']
        kwargs['source_package_name'] = (
            SourcePackageName.objects.get_or_create(name=name)[0])
    if 'version' in arguments:
        kwargs['version'] = arguments['version']
    if 'directory' in arguments:
        kwargs['directory'] = arguments['directory']
    if 'dsc_file_name' in arguments:
        kwargs['dsc_file_name'] = arguments['dsc_file_name']

    src_pkg = SourcePackage.objects.create(**kwargs)

    # Now add m2m fields
    if 'architectures' in arguments:
        architectures = arguments['architectures']
        src_pkg.architectures = Architecture.objects.filter(
            name__in=architectures)
    if 'binary_packages' in arguments:
        binaries = []
        for binary in arguments['binary_packages']:
            binaries.append(
                BinaryPackageName.objects.get_or_create(name=binary)[0])
        src_pkg.binary_packages = binaries

    src_pkg.save()
    return src_pkg


def set_mock_response(mock_requests, text="", headers=None, status_code=200):
    """
    Helper method which sets a mock response to the given mock requests
    module.

    It takes care to correctly set the return value of all useful requests
    module functions.

    :param mock_requests: A mock requests module.
    :param text: The text of the response.
    :param headers: The headers of the response.
    :param status_code: The status code of the response.
    """
    if headers is None:
        headers = {}
    mock_response = mock_requests.models.Response()
    mock_response.headers = headers
    mock_response.status_code = status_code
    mock_response.ok = status_code < 400
    mock_response.text = text
    mock_response.content = text.encode('utf-8')
    mock_response.iter_lines.return_value = text.splitlines()
    mock_requests.get.return_value = mock_response
