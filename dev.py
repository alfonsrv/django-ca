#!/usr/bin/env python3
#
# This file is part of django-ca (https://github.com/mathiasertl/django-ca).
#
# django-ca is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# django-ca is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-ca.  If not,
# see <http://www.gnu.org/licenses/>.

"""Various commands used in development."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
import warnings

import packaging.version

import cryptography
from cryptography import x509
from cryptography.hazmat.backends import default_backend

import django
from django.core.exceptions import ImproperlyConfigured

from common import CADIR
from common import ROOTDIR
from common import bold
from common import error
from common import ok
from common import setup_django

test_base = argparse.ArgumentParser(add_help=False)
test_base.add_argument('-s', '--suites', default=[], nargs='+',
                       help="Modules to test (e.g. tests_modules).")
selenium_grp = test_base.add_argument_group('Selenium tests')
selenium_grp.add_argument('--no-selenium', dest='selenium', action='store_false', default=True,
                          help='Do not run selenium tests at all.')
selenium_grp.add_argument('-p', '--no-virtual-display', dest='virtual_display', action='store_false',
                          default=True, help="Do not run tests in virtual display.")

parser = argparse.ArgumentParser(
    description='Helper-script for various tasks during development.'
)
commands = parser.add_subparsers(dest='command')
cq_parser = commands.add_parser('code-quality', help='Run various checks for coding standards.')
ti_parser = commands.add_parser('test-imports', help='Import django-ca modules to test dependencies.')
dt_parser = commands.add_parser('docker-test', help='Build the Docker image using various base images.')
dt_parser.add_argument('-i', '--image', action='append', dest='images',
                       help='Base images to test on, may be given multiple times.')
dt_parser.add_argument('--no-cache', default=False, action='store_true',
                       help='Use Docker cache to speed up builds.')
dt_parser.add_argument('--fail-fast', action='store_true', default=False,
                       help='Stop if any docker process fails.')
dt_parser.add_argument('--keep-image', action='store_true', default=False,
                       help='Do not remove images..')

test_parser = commands.add_parser('test', parents=[test_base])
cov_parser = commands.add_parser('coverage', parents=[test_base])
cov_parser.add_argument('-f', '--format', choices=['html', 'text'], default='html',
                        help='Write coverage report as text (default: %(default)s).')
cov_parser.add_argument('--fail-under', type=int, default=100, metavar='[0-100]',
                        help='Fail if coverage is below given percentage (default: %(default)s%%).')

demo_parser = commands.add_parser('init-demo', help="Initialize the demo data.")
demo_parser.add_argument('--base-url', metavar='URL', default='http://localhost:8000/',
                         help="Base URL for CRL/OCSP URLs.")

commands.add_parser('collectstatic', help="Collect and remove static files.")
commands.add_parser('clean', help="Remove generated files.")
args = parser.parse_args()


def test(suites):
    """Run named test suites (or all of them)."""
    # pylint: disable=import-outside-toplevel; imported here so that script runs without django
    from django.core.management import call_command  # pylint: disable=redefined-outer-name
    from django.utils import deprecation

    # pylint: enable=import-outside-toplevel

    if not args.virtual_display:
        os.environ['VIRTUAL_DISPLAY'] = 'n'

    warnings.filterwarnings(action='always')
    warnings.filterwarnings(action='error', module='django_ca')

    # ignore this warning in some modules to get cleaner output

    # filter some webtest warnings
    msg2 = r'urllib.parse.splithost\(\) is deprecated as of 3.8, use urllib.parse.urlparse\(\) instead'
    msg3 = r'urllib.parse.splittype\(\) is deprecated as of 3.8, use urllib.parse.urlparse\(\) instead'
    warnings.filterwarnings(action='ignore', category=DeprecationWarning, module='webtest.*', message=msg2)
    warnings.filterwarnings(action='ignore', category=DeprecationWarning, module='webtest.*', message=msg3)

    # At present, some libraries are not yet updated.
    if hasattr(deprecation, 'RemovedInDjango40Warning'):  # pragma: django<=3.0
        warnings.filterwarnings(
            action='ignore', category=deprecation.RemovedInDjango40Warning,
            module='django_object_actions.utils',
            message=r'^django\.conf\.urls\.url\(\) is deprecated in favor of django\.urls\.re_path\(\)\.$'
        )

    os.chdir(CADIR)
    sys.path.insert(0, CADIR)

    suites = ['django_ca.tests.%s' % s.strip('.') for s in suites]

    call_command('test', *suites, parallel=True)


def exclude_versions(cov, sw, this_version, version, version_str):
    if version == this_version:
        cov.exclude(r'pragma: only %s>%s' % (sw, version_str))
        cov.exclude(r'pragma: only %s<%s' % (sw, version_str))
    else:
        cov.exclude(r'pragma: only %s==%s' % (sw, version_str))

        if version > this_version:
            cov.exclude(r'pragma: only %s>=%s' % (sw, version_str))
            cov.exclude(r'pragma: only %s>%s' % (sw, version_str))

        if version < this_version:
            cov.exclude(r'pragma: only %s<=%s' % (sw, version_str))
            cov.exclude(r'pragma: only %s<%s' % (sw, version_str))


if args.command == 'test':
    if not args.selenium:
        os.environ['SKIP_SELENIUM_TESTS'] = 'y'

    setup_django()
    test(args.suites)
elif args.command == 'coverage':
    import coverage

    if 'TOX_ENV_DIR' in os.environ:
        report_dir = os.path.join(os.environ['TOX_ENV_DIR'], 'coverage')
        data_file = os.path.join(os.environ['TOX_ENV_DIR'], '.coverage')
    else:
        report_dir = os.path.join(ROOTDIR, 'docs', 'build', 'coverage')
        data_file = None

    if not args.selenium:
        os.environ['SKIP_SELENIUM_TESTS'] = 'y'

    cov = coverage.Coverage(data_file=data_file, cover_pylib=False, branch=True, source=['django_ca'],
                            omit=['*migrations/*', '*/tests/tests*', ])

    # exclude python version specific code
    py_versions = [(3, 5), (3, 6), (3, 7), (3, 8), (3, 9)]
    for version in py_versions:
        version_str = '.'.join([str(v) for v in version])
        exclude_versions(cov, 'py', sys.version_info[:2], version, version_str)

    # exclude django-version specific code
    django_versions = [(2, 2), (3, 0), (3, 1)]
    for version in django_versions:
        version_str = '.'.join([str(v) for v in version])
        exclude_versions(cov, 'django', django.VERSION[:2], version, version_str)

    # exclude cryptography-version specific code
    this_version = packaging.version.parse(cryptography.__version__).release[:2]
    cryptography_versions = [(2, 7), (2, 8), (2, 9), (3, 0), (3, 1)]
    for ver in cryptography_versions:
        version_str = '.'.join([str(v) for v in ver])
        exclude_versions(cov, 'cryptography', this_version, ver, version_str)

    cov.exclude(r'^\s*if TYPE_CHECKING:')

    cov.start()

    setup_django()
    test(args.suites)

    cov.stop()
    cov.save()

    if args.format == 'text':
        total_coverage = cov.report()
    else:
        total_coverage = cov.html_report(directory=report_dir)
    if total_coverage < args.fail_under:
        if args.fail_under == 100.0:
            print('Error: Coverage was only %.2f%% (should be 100%%).' % total_coverage)
        else:
            print('Error: Coverage was only %.2f%% (should be above %.2f%%).' % (
                total_coverage, args.fail_under))
        sys.exit(2)  # coverage cli utility also exits with 2

elif args.command == 'code-quality':
    files = ['ca/', 'setup.py', 'dev.py', 'recreate-fixtures.py']
    print('isort --check-only --diff %s' % ' '.join(files))
    subprocess.run(['isort', '--check-only', '--diff'] + files, check=True)

    print('flake8 %s' % ' '.join(files))
    subprocess.run(['flake8'] + files, check=True)

    print('python -Wd manage.py check')
    subprocess.run(['python', '-Wd', 'manage.py', 'check'], cwd=CADIR, check=True,
                   env=dict(os.environ, DJANGO_CA_SECRET_KEY='dummy'))
elif args.command == 'test-imports':
    setup_django('ca.settings')

    # pylint: disable=ungrouped-imports; have to call setup_django() first
    # pylint: disable=unused-import; this command just tests if import is working

    # useful when run in docker-test, where localsettings uses YAML
    from django.conf import settings  # NOQA: F401

    # import some modules - if any dependency is not installed, this will fail
    from django_ca import extensions  # NOQA: F401
    from django_ca import models  # NOQA: F401
    from django_ca import subject  # NOQA: F401
    from django_ca import tasks  # NOQA: F401
    from django_ca import utils  # NOQA: F401
    from django_ca import views  # NOQA: F401

    # pylint: enable=ungrouped-imports,unused-import

elif args.command == 'docker-test':
    images = args.images or [
        'default',

        # Currently supported Alpine releases:
        #   https://wiki.alpinelinux.org/wiki/Alpine_Linux:Releases

        'python:3.6-alpine3.12',
        'python:3.7-alpine3.12',
        'python:3.8-alpine3.12',
        'python:3.9-alpine3.12',
        'python:3.6-alpine3.11',
        'python:3.7-alpine3.11',
        'python:3.8-alpine3.11',
    ]

    docker_runs = []

    for image in images:
        print('### Testing %s ###' % image)
        tag = 'django-ca-test-%s' % image

        cmd = ['docker', 'build', ]

        if args.no_cache:
            cmd.append('--no-cache')
        if image != 'default':
            cmd += ['--build-arg', 'IMAGE=%s' % image, ]

        cmd += ['-t', tag, ]
        cmd.append('.')

        print(' '.join(cmd))

        logdir = '.docker'
        logpath = os.path.join(logdir, '%s.log' % image)
        if not os.path.exists(logdir):
            os.makedirs(logdir)

        env = dict(os.environ, DOCKER_BUILDKIT='1')

        try:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env) as p, \
                    open(logpath, 'bw') as stream:
                while True:
                    byte = p.stdout.read(1)
                    if byte:
                        sys.stdout.buffer.write(byte)
                        sys.stdout.flush()
                        stream.write(byte)
                        # logfile.flush()
                    else:
                        break

            if p.returncode == 0:
                ok_str = '# %s passed. #' % image
                ok("%s\n%s\n%s\n\n" % ('#' * len(ok_str), ok_str, '#' * len(ok_str)))
                docker_runs.append({
                    'image': image,
                    'success': True,
                    'error': '',
                })
            else:
                failed_str = '# %s failed: return code %s. #' % (image, p.returncode)
                error("%s\n%s\n%s\n\n" % ('#' * len(failed_str), failed_str, '#' * len(failed_str)))
                docker_runs.append({
                    'image': image,
                    'success': False,
                    'error': 'return code: %s' % p.returncode,
                })

        except Exception as e:  # pylint: disable=broad-except; to make sure we test all images
            msg = '%s: %s: %s' % (image, type(e).__name__, e)
            docker_runs.append({
                'image': image,
                'success': False,
                'error': msg,
            })

            error("\n%s\n" % msg)
            if args.fail_fast:
                sys.exit(1)
        finally:
            if not args.keep_image:
                subprocess.call(['docker', 'image', 'rm', tag])

    print("\nSummary of test runs:")
    for run in docker_runs:
        if run['success']:
            ok('  %s: passed.' % run['image'])
        else:
            error('  %s: %s' % (run['image'], run['error']))

    failed_images = [r for r in docker_runs if r['success']]
    if not failed_images:
        ok("\nCongratulations :)")
    else:
        error("\nSome images failed (%s)" % ', '.join(failed_images))
        sys.exit(1)

elif args.command == 'init-demo':
    os.environ['DJANGO_CA_SECRET_KEY'] = 'dummy'

    if 'TOX_ENV_DIR' in os.environ:
        os.environ['DJANGO_CA_SKIP_LOCAL_CONFIG'] = '1'
        os.environ['CA_DIR'] = os.environ['TOX_ENV_DIR']
        os.environ['SQLITE_NAME'] = os.path.join(os.environ['TOX_ENV_DIR'], 'db.sqlite3')

    try:
        setup_django('ca.settings')
    except ImproperlyConfigured:
        # Cannot import settings, probably because localsettings.py wasn't created.
        traceback.print_exc()
        localsettings = os.path.join(CADIR, 'ca', 'localsettings.py')
        print("""
Could not configure settings! Have you created localsettings.py?

Please create %(localsettings)s from %(example)s and try again.""" % {
            'localsettings': localsettings,
            'example': '%s.example' % localsettings,
        })
        sys.exit(1)

    # pylint: disable=ungrouped-imports; have to call setup_django() first
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from django.core.management import call_command as manage
    from django.urls import reverse

    from django_ca import ca_settings
    from django_ca.models import Certificate
    from django_ca.models import CertificateAuthority
    from django_ca.utils import ca_storage

    # pylint: enable=ungrouped-imports

    User = get_user_model()

    print('Creating database...', end='')
    manage('migrate', verbosity=0)
    ok()

    if not os.path.exists(ca_settings.CA_DIR):
        os.makedirs(ca_settings.CA_DIR)

    # NOTE: We pass SKIP_SELENIUM_TESTS=y as environment, because otherwise test_settings will complain that
    #       the driver isn't there, when in fact we're not running any tests.
    print('Creating fixture data...', end='')
    subprocess.check_call(['python', 'recreate-fixtures.py', '--no-delay', '--no-ocsp', '--no-contrib',
                           '--ca-validity=3650', '--cert-validity=732',
                           '--dest=%s' % ca_settings.CA_DIR], env=dict(os.environ, SKIP_SELENIUM_TESTS='y'))
    with open(os.path.join(ca_settings.CA_DIR, 'cert-data.json')) as stream:
        fixture_data = json.load(stream)
    ok()

    print('Saving fixture data to database.', end='')
    loaded_cas = {}
    certs = fixture_data['certs']
    for cert_name, cert_data in sorted(certs.items(), key=lambda t: (t[1]['type'], t[0])):
        if cert_data['type'] == 'ca':
            if not cert_data['key_filename']:
                continue  # CA without private key (e.g. real-world CA)

            name = cert_data['name']
            path = '%s.key' % name

            with open(os.path.join(ca_settings.CA_DIR, cert_data['key_filename']), 'rb') as stream:
                pkey = stream.read()

            c = CertificateAuthority(name=name, private_key_path=path)
            loaded_cas[c.name] = c
        else:
            if cert_data['cat'] != 'generated':
                continue  # Imported cert

            with open(os.path.join(ca_settings.CA_DIR, cert_data['csr_filename']), 'r') as stream:
                csr = stream.read()
            profile = cert_data.get('profile', ca_settings.CA_DEFAULT_PROFILE)
            c = Certificate(ca=loaded_cas[cert_data['ca']], csr=csr, profile=profile)

        with open(os.path.join(ca_settings.CA_DIR, cert_data['pub_filename']), 'rb') as stream:
            pem = stream.read()
        c.x509 = x509.load_pem_x509_certificate(pem, default_backend())

        c.save()

        if cert_data['type'] == 'ca':
            password = cert_data.get('password')
            if password is not None:
                password = password.encode('utf-8')
            c.generate_ocsp_key(password=password)

    # create admin user for login
    User.objects.create_superuser('user', 'user@example.com', 'nopass')

    ok()

    # create a chain file for the child
    chain = loaded_cas['child'].pub + loaded_cas['root'].pub
    chain_path = ca_storage.path(ca_storage.save('child-chain.pem', ContentFile(chain)))

    cwd = os.getcwd()
    rel = lambda p: os.path.relpath(p, cwd)  # NOQA
    root_ca_path = ca_storage.path(certs['root']['pub_filename'])
    child_ca_path = ca_storage.path(certs['child']['pub_filename'])

    root_cert_path = ca_storage.path(certs['root-cert']['pub_filename'])
    child_cert_path = ca_storage.path(certs['child-cert']['pub_filename'])

    ocsp_url = '%s%s' % (args.base_url.rstrip('/'),
                         reverse('django_ca:ocsp-cert-post', kwargs={'serial': certs['child']['serial']}))

    print("")
    print('* All certificates are in %s.' % bold(ca_settings.CA_DIR))
    ok('* Start webserver with the admin interface:')
    print('  * Run "%s"' % bold('python ca/manage.py runserver'))
    print('  * Visit %s' % bold('%sadmin/' % args.base_url))
    print('  * User/Password: %s / %s' % (bold('user'), bold('nopass')))
    ok('* Create CRLs with:')
    print('  * %s' % bold('python ca/manage.py dump_crl -f PEM --ca %s > root.crl' %
                          loaded_cas['root'].serial[:11]))
    print('  * %s' % bold('python ca/manage.py dump_crl -f PEM --ca %s > child.crl' %
                          loaded_cas['child'].serial[:11]))
    ok('* Verify with CRL:')
    print('  * %s' % bold('openssl verify -CAfile %s -CRLfile root.crl -crl_check %s' % (
                          rel(root_ca_path), rel(root_cert_path))))
    print('  * %s' % bold('openssl verify -CAfile %s -crl_download -crl_check %s' % (
                          rel(root_ca_path), rel(root_cert_path))))
    ok('* Verify certificate with OCSP:')
    print('    %s' % bold('openssl ocsp -CAfile %s -issuer %s -cert %s -url %s -resp_text' % (
        rel(root_ca_path), rel(child_ca_path), rel(child_cert_path), ocsp_url)))

elif args.command == 'collectstatic':
    setup_django('ca.settings')

    # pylint: disable=ungrouped-imports; have to call setup_django() first
    from django.contrib.staticfiles.finders import get_finders
    from django.core.management import call_command

    # pylint: enable=ungrouped-imports

    call_command('collectstatic', interactive=False)

    locations = set()
    for finder in get_finders():
        for path, storage in finder.list([]):
            locations.add(storage.location)

    for location in locations:
        print('rm -r "%s"' % location)
        shutil.rmtree(location)
elif args.command == 'clean':
    base = os.path.dirname(os.path.abspath(__file__))

    def rm(*paths):  # pylint: disable=invalid-name; rm() is just descriptive
        """Remove a file/dir if it exists."""
        rm_path = os.path.join(base, *paths)
        if not os.path.exists(rm_path):
            return
        if os.path.isdir(rm_path):
            print('rm -r', rm_path)
            shutil.rmtree(rm_path)
        else:
            print('rm', rm_path)
            os.remove(rm_path)

    rm('pip-selfcheck.json')
    rm('geckodriver.log')
    rm('docs', 'build')
    rm('.tox')
    rm('ca', 'files')
    rm('ca', 'geckodriver.log')
    rm('dist')
    rm('build')
    rm('.coverage')
    rm('.docker')

    for root, dirs, files in os.walk(base, topdown=False):
        for name in files:
            if name.endswith('.pyc') or name.endswith('.sqlite3'):
                rm(root, name)
        for name in dirs:
            if name == '__pycache__' or name.endswith('.egg-info'):
                rm(root, name)

else:
    parser.print_help()
